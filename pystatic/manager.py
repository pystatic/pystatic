import os
import logging
from collections import deque
from typing import Dict, Deque, Set
from pystatic.config import Config
from pystatic.infer.infer_expr import infer_expr
from pystatic.error.errorcode import *
from pystatic.error.errorbox import ErrorBox
from pystatic.fsys import Filesys, FilePath, ModuleFindRes
from pystatic.infer.infer import InferStarter
from pystatic.result import Result
from pystatic.preprocess import Preprocessor
from pystatic.predefined import *
from pystatic.symid import SymId, relpath2symid
from pystatic.typesys import TypeIns
from pystatic.predefined import TypeModuleIns
from pystatic.target import BlockTarget, Target, Stage, PackageTarget
from pystatic.symtable import SymTable, TableScope

logger = logging.getLogger(__name__)


class Manager:
    def __init__(self, config: Config):
        self.config = config

        self.fsys = Filesys(config)

        self.pre_proc = Preprocessor(self)
        self.to_check: Set[SymId] = set()  # modules that need to be checked
        self.targets: Dict[SymId, Target] = {}

        self.q_preprocess: Deque[BlockTarget] = deque()
        self.q_infer: Deque[BlockTarget] = deque()

        self.manager_errbox = ErrorBox(MANAGER_TAG)
        self.message_cache: Dict[SymId, List[Message]] = {}

        if not config.no_typeshed:
            self.__init_typeshed()

    def __init_typeshed(self):
        self.__add_check_symid("builtins", builtins_symtable, False, None, True)
        self.__add_check_symid("typing", typing_symtable, False, None, True)
        self.__add_check_symid(
            "typing_extensions", typing_extensions_symtable, False, None, True
        )
        self.preprocess()

    def get_abspath(self, symid: "SymId") -> Optional[List[str]]:
        """
        Get absolute path of the symid, note that a symid may match multiple paths.
        symid may not be added to check.
        """
        find_res = self.fsys.find_module(symid)
        if not find_res:
            return None
        else:
            return find_res.paths

    def get_symid(self, path: str) -> Optional[SymId]:
        """Convert a path to symid"""
        return self.fsys.path_to_symid(path)

    def get_target(self, symid: "SymId") -> Optional[Target]:
        return self.targets.get(symid, None)

    def __add_check_symid(
        self,
        symid: "SymId",
        default_symtable: Optional["SymTable"],
        to_check: bool,
        oldpath: Optional[FilePath],
        is_special: bool,
    ) -> Result[bool]:
        """
        @param default_symtable: if not None, then the symtable of the new target is set to it.

        @param oldpath: if not None, then it is the path that find_module should return.
        """
        if symid in self.targets:
            return Result(False)

        find_res = self.fsys.find_module(symid)
        add_result = Result(True)
        if not find_res:
            add_result.value = False
            add_result.add_err(ModuleNotFound(symid))

        else:
            if default_symtable:
                symtable = default_symtable
            else:
                # Generate new symtable for the new target
                symtable = SymTable(
                    symid, None, None, builtins_symtable, self, TableScope.GLOB
                )
                symtable.glob = symtable
            errbox = ErrorBox(symid)

            # TODO: support namespace
            assert len(find_res.paths) == 1

            assert not oldpath or os.path.isabs(oldpath)

            find_res.paths[0] = self.fsys.abspath(find_res.paths[0])
            assert os.path.isabs(find_res.paths[0])
            if oldpath and os.path.normcase(oldpath) != os.path.normcase(
                find_res.paths[0]
            ):
                # TODO: report name collision
                add_result = Result(False)
                return add_result

            if find_res.res_type == ModuleFindRes.Module:
                file_path = self.fsys.realpath(find_res.paths[0])
                new_target = Target(
                    symid, symtable, errbox, file_path, is_special=is_special
                )

                self.__parse(new_target)
                self.update_stage(new_target, Stage.Preprocess)
                self.__add_target(new_target, to_check)

            elif find_res.res_type == ModuleFindRes.Package:
                assert find_res.analyse_path
                dir_path = self.fsys.realpath(find_res.paths[0])
                analyse_path = self.fsys.realpath(find_res.analyse_path)

                assert dir_path == os.path.dirname(analyse_path)

                # modify symtable's symid to the symid of the module preprocessed
                # to handle relative import correctly
                symtable.symid = symtable.symid + ".__init__"

                new_target = PackageTarget(
                    symid, symtable, errbox, dir_path, analyse_path
                )
                new_target.module_ins = TypePackageIns(
                    new_target.symtable, find_res.paths, None
                )
                new_target.path = self.fsys.realpath(find_res.paths[0])

                self.__parse(new_target)
                self.update_stage(new_target, Stage.Preprocess)
                self.__add_target(new_target, to_check)

            elif find_res.res_type == ModuleFindRes.Namespace:
                return Result(False)
                assert False, "Namespace package not supported yet"

        return add_result

    def __add_target(self, target: Target, to_check: bool):
        """Add target"""
        self.targets[target.symid] = target
        if target.path:
            self.fsys.add_path_symid_map(target.path, target.symid)
        if to_check:
            self.to_check.add(target.symid)

    def __parse(self, target: Target):
        assert target.stage == Stage.Parse
        assert os.path.isabs(target.analyse_path)
        target.ast = path2ast(target.analyse_path)

    def is_module(self, symid: "SymId") -> bool:
        """symid represents a valid module?"""
        find_res = self.fsys.find_module(symid)
        if not find_res:
            return False
        else:
            return True

    def is_on_check(self, symid: "SymId") -> bool:
        return symid in self.to_check

    def update_stage(self, target: BlockTarget, stage: Stage, isnew: bool = False):
        """Update the stage of a target

        @param ifnew: True if target is not in self.targets.

        If target's original stage is equal to the new stage and isnew is false,
        then nothing will happen.
        """
        if target.stage == stage and not isnew:
            return
        target.stage = stage
        if stage == Stage.Parse:
            assert isinstance(target, Target)
            self.__parse(target)
        elif stage == Stage.Preprocess:
            self.q_preprocess.append(target)
        elif stage == Stage.Infer:
            self.q_infer.append(target)
        elif stage == Stage.FINISH:
            pass

    def get_module_ins(self, symid: "SymId") -> Optional[TypeModuleIns]:
        if symid in self.targets:
            return self.targets[symid].module_ins
        return None

    def add_check_file(
        self, path: FilePath, to_check: bool = True, recheck: bool = False
    ) -> Result[bool]:
        path = self.fsys.realpath(path)

        if not os.path.exists(path):
            add_result = Result(False)
            add_result.add_err(FileNotFound(path))
            return add_result
        else:
            rt_path = crawl_path(os.path.dirname(path))
            self.fsys.add_userpath(rt_path)
            symid = relpath2symid(rt_path, path)
            if recheck and symid in self.targets:
                return self.recheck(symid)
            return self.__add_check_symid(symid, None, to_check, path, False)

    def add_check_symid(self, symid: "SymId", to_check: bool = True) -> Result[bool]:
        return self.__add_check_symid(symid, None, to_check, None, False)

    def add_check_target(self, target: "BlockTarget", to_check: bool = True):
        if isinstance(target, Target):
            assert target not in self.targets
            self.__add_target(target, to_check)
        self.update_stage(target, target.stage, True)

    def send(self, tag: str, msg: Message):
        if tag in self.message_cache:
            self.message_cache[tag].append(msg)
        elif tag in self.targets:
            self.message_cache[tag] = [msg]

    def take_messages_by_symid(self, symid: "SymId") -> Sequence[Message]:
        """Get messages according to the symid"""
        self.manager_errbox.release(self)
        target = self.targets.get(symid)
        if target:
            target.errbox.release(self)
        elif symid.endswith(".__init__"):
            package_id = symid[: -len(".__init__")]
            if (target := self.targets.get(package_id)) :
                target.errbox.release(self)
        else:
            return []
        if (res := self.message_cache.get(symid, None)) :
            self.message_cache[symid] = []
            return sorted(res)
        else:
            return []

    def take_messages(self, path: FilePath) -> Sequence[Message]:
        """Get messages according to a absolute file path"""
        path = os.path.normcase(path)
        symid = self.fsys.path_to_symid(path)
        if symid:
            return self.take_messages_by_symid(symid)
        return []

    def take_all_messages(self) -> Dict[SymId, List[Message]]:
        self.manager_errbox.release(self)
        for target in self.targets.values():
            target.errbox.release(self)
        tmp_messages = self.message_cache
        self.message_cache = {}
        return tmp_messages

    def preprocess(self):
        self.pre_proc.process()
        pass

    def preprocess_block(self, blk_target: BlockTarget):
        self.update_stage(blk_target, Stage.Preprocess, True)
        self.pre_proc.process()
        pass

    def infer(self):
        InferStarter(self.q_infer, self.config, self).start_infer()

    def infer_expr(self, module_symid: SymId, expr: str) -> Optional["TypeIns"]:
        """Evaluate an expression of a in the environment of a module"""
        try:
            astnode = ast.parse(expr, mode="eval")
            module_ins = self.get_module_ins(module_symid)
            if not module_ins:
                return None
            result = infer_expr(astnode.body, module_ins)  # type: ignore
            if result.haserr():
                return None
            else:
                return result.value
        except SyntaxError as e:
            return None

    def recheck(self, module_symid: SymId, from_begin: bool = True) -> Result[bool]:
        """Recheck a module, this will flush old message of that module automatically"""
        module_target = self.targets.get(module_symid)
        assert isinstance(module_target, Target)
        if from_begin:
            try:
                new_ast = path2ast(module_target.path)
                module_target.ast = new_ast
                module_target.clear()
                self.update_stage(module_target, Stage.Preprocess, False)
                return Result(True)
            except SyntaxError:
                return Result(False)
        else:
            self.update_stage(module_target, Stage.Preprocess, False)
            return Result(True)


def path2ast(path: FilePath) -> ast.AST:
    with open(path, "r") as f:
        content = f.read()
        return ast.parse(content, type_comments=True)


def crawl_path(path: str) -> str:
    """Move up the directory until find a directory that doesn't contains __init__.py.

    This may fail when analysing a namespace package.
    """
    while True:
        init_file = os.path.join(path, "__init__.py")
        if os.path.isfile(init_file):
            dirpath = os.path.dirname(path)
            if path == dirpath:
                # TODO: warning here
                break
            else:
                path = dirpath
        else:
            break
    return path
