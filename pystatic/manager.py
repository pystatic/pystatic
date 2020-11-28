import os
import logging
from collections import deque
from typing import Optional, Dict, Deque, Set
from pystatic.config import Config
from pystatic.exprparse import eval_expr
from pystatic.errorcode import *
from pystatic.fsys import Filesys, FilePath, ModuleFindRes
from pystatic.infer.infer import InferStarter
from pystatic.message import MessageBox
from pystatic.option import Option
from pystatic.preprocess import Preprocessor
from pystatic.predefined import TypePackageIns, builtins_symtable, typing_symtable
from pystatic.symid import SymId, relpath2symid, symid2list
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

        if not config.no_typeshed:
            self.__init_typeshed()

    def __init_typeshed(self):
        self.__add_check_symid('builtins', builtins_symtable, False, None,
                               True)
        self.__add_check_symid('typing', typing_symtable, False, None, True)
        self.preprocess()

    def __add_check_symid(self, symid: 'SymId',
                          default_symtable: Optional['SymTable'],
                          to_check: bool, oldpath: Optional[FilePath],
                          is_special: bool) -> Option[bool]:
        """
        default_symtable:
            if not None, then the symtable of the new target is set to it.

        oldpath:
            if not None, then it is the path that find_module should return.
        """
        if symid in self.targets:
            return Option(False)

        find_res = self.fsys.find_module(symid)
        add_option = Option(True)
        if not find_res:
            add_option.value = False
            add_option.add_error(ModuleNotFound(symid))

        else:
            if default_symtable:
                symtable = default_symtable
            else:
                # Generate new symtable for the new target
                symtable = SymTable(symid, None, None, builtins_symtable, self,
                                    TableScope.GLOB)
                symtable.glob = symtable
            mbox = MessageBox(symid)

            # TODO: support namespace
            assert len(find_res.paths) == 1

            assert (not oldpath or os.path.isabs(oldpath))

            find_res.paths[0] = self.fsys.abspath(find_res.paths[0])
            assert os.path.isabs(find_res.paths[0])
            if oldpath and os.path.normcase(oldpath) != os.path.normcase(
                    find_res.paths[0]):
                # TODO: report name collision
                add_option = Option(False)
                return add_option

            if find_res.res_type == ModuleFindRes.Module:
                file_path = self.fsys.realpath(find_res.paths[0])
                new_target = Target(symid,
                                    symtable,
                                    mbox,
                                    file_path,
                                    is_special=is_special)

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
                symtable.symid = symtable.symid + '.__init__'

                new_target = PackageTarget(symid, symtable, mbox, dir_path,
                                           analyse_path)
                new_target.module_ins = TypePackageIns(new_target.symtable,
                                                       find_res.paths, None)
                new_target.path = self.fsys.realpath(find_res.paths[0])

                self.__parse(new_target)
                self.update_stage(new_target, Stage.Preprocess)
                self.__add_target(new_target, to_check)

            elif find_res.res_type == ModuleFindRes.Namespace:
                assert False, "Namespace package not supported yet"

        return add_option

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

    def is_module(self, symid: 'SymId') -> bool:
        """symid represents a valid module?"""
        find_res = self.fsys.find_module(symid)
        if not find_res:
            return False
        else:
            return True

    def is_on_check(self, symid: 'SymId') -> bool:
        return symid in self.to_check

    def update_stage(self,
                     target: BlockTarget,
                     stage: Stage,
                     isnew: bool = False):
        """Update the stage of a target

        ifnew:
            True if target is not in self.targets.

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

    def get_module_ins(self, symid: 'SymId') -> Optional[TypeModuleIns]:
        if symid in self.targets:
            return self.targets[symid].module_ins
        return None

    def add_check_file(self,
                       path: FilePath,
                       to_check: bool = True,
                       recheck: bool = False) -> Option[bool]:
        path = self.fsys.realpath(path)

        if not os.path.exists(path):
            add_option = Option(False)
            add_option.add_error(FileNotFound(path))
            return add_option
        else:
            rt_path = crawl_path(os.path.dirname(path))
            self.fsys.add_userpath(rt_path)
            symid = relpath2symid(rt_path, path)
            if recheck and symid in self.targets:
                return self.recheck(symid)
            return self.__add_check_symid(symid, None, to_check, path, False)

    def add_check_symid(self,
                        symid: 'SymId',
                        to_check: bool = True) -> Option[bool]:
        return self.__add_check_symid(symid, None, to_check, None, False)

    def add_check_target(self, target: 'BlockTarget', to_check: bool = True):
        if isinstance(target, Target):
            assert target not in self.targets
            self.__add_target(target, to_check)
        self.update_stage(target, target.stage, True)

    def change_target_stage(self, target: 'Target', stage: Stage):
        assert target == self.targets.get(target.symid)
        self.update_stage(target, stage)

    def get_mbox_by_symid(self, symid: 'SymId') -> Optional[MessageBox]:
        target = self.targets.get(symid)
        if target:
            return target.mbox
        elif symid.endswith('.__init__'):
            package_id = symid[:-len('.__init__')]
            if (target := self.targets.get(package_id)):
                return target.mbox

    def get_mbox(self, path: FilePath) -> Optional[MessageBox]:
        path = os.path.normcase(path)
        symid = self.fsys.path_to_symid(path)
        if symid:
            return self.get_mbox_by_symid(symid)
        return None

    def preprocess(self):
        self.pre_proc.process()
        pass

    def preprocess_block(self, blk_target: BlockTarget):
        self.update_stage(blk_target, Stage.Preprocess, True)
        self.pre_proc.process()
        pass

    def infer(self):
        InferStarter(self.q_infer, self.config, self).start_infer()

    def get_sym_type(self, module_symid: SymId,
                     var_symid: SymId) -> Optional['TypeIns']:
        module_ins = self.get_module_ins(module_symid)
        if not module_ins:
            return None
        else:
            varid_list = symid2list(var_symid)
            cur_ins = module_ins
            for subid in varid_list:
                res_option = cur_ins.getattribute(subid, None)
                if res_option.haserr():
                    return None
                cur_ins = res_option.value
            return cur_ins

    def eval_expr(self, module_symid: SymId, expr: str) -> Optional['TypeIns']:
        try:
            astnode = ast.parse(expr, mode='eval')
            module_ins = self.get_module_ins(module_symid)
            if not module_ins:
                return None
            res_option = eval_expr(astnode.body, module_ins)  # type: ignore
            if res_option.haserr():
                return None
            else:
                return res_option.value
        except SyntaxError as e:
            return None

    def recheck(self, module_symid: SymId) -> Option[bool]:
        module_target = self.targets.get(module_symid)
        assert isinstance(module_target, Target)
        try:
            new_ast = path2ast(module_target.path)
            module_target.ast = new_ast
            module_target.clear()
            self.update_stage(module_target, Stage.Preprocess, False)
            return Option(True)
        except SyntaxError:
            return Option(False)


def path2ast(path: FilePath) -> ast.AST:
    with open(path, 'r') as f:
        content = f.read()
        return ast.parse(content, type_comments=True)


def crawl_path(path: str) -> str:
    """Move up the directory until find a directory that doesn't contains __init__.py.

    This may fail when analysing a namespace package.
    """
    while True:
        init_file = os.path.join(path, '__init__.py')
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
