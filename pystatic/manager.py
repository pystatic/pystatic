import os
import logging
from collections import deque
from typing import Optional, Dict, TYPE_CHECKING, Deque
from pystatic.config import Config
from pystatic.exprparse import eval_expr
from pystatic.errorcode import *
from pystatic.fsys import Filesys, FilePath, ModuleFindRes
from pystatic.infer.infer import InferStarter
from pystatic.message import MessageBox
from pystatic.option import Option
from pystatic.preprocess import Preprocessor
from pystatic.predefined import (get_builtin_symtable, get_typing_symtable,
                                 get_init_module_symtable)
from pystatic.symid import SymId, relpath2symid, symid2list
from pystatic.typesys import (TypeModuleTemp, TypePackageTemp, TypeIns,
                              any_ins)
from pystatic.target import BlockTarget, Mode, Target, Stage, PackageTarget

if TYPE_CHECKING:
    from pystatic.symtable import SymTable

logger = logging.getLogger(__name__)


class Manager:
    def __init__(self, config: Config):
        self.config = config

        self.fsys = Filesys(config)

        self.pre_proc = Preprocessor(self)
        self.targets: Dict[SymId, Target] = {}

        self.q_preprocess: Deque[BlockTarget] = deque()
        self.q_infer: Deque[BlockTarget] = deque()

        if not config.no_typeshed:
            self.__init_typeshed()

    def __init_typeshed(self):
        self.__add_check_symid('builtins', get_builtin_symtable())
        self.__add_check_symid('typing', get_typing_symtable())
        self.preprocess()

    def __add_check_symid(self,
                          symid: 'SymId',
                          default_symtable: Optional['SymTable'] = None,
                          oldpath: Optional[FilePath] = None,
                          mode: Mode = Mode.Normal) -> Option[bool]:
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
            add_option.add_err(ModuleNotFound(symid))

        else:
            if default_symtable:
                symtable = default_symtable
            else:
                symtable = get_init_module_symtable(symid)
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
                                    mode=mode)

                self.__parse(new_target)
                self.update_stage(new_target, Stage.Preprocess)
                self.__add_target(new_target)

            elif find_res.res_type == ModuleFindRes.Package:
                assert find_res.analyse_path
                dir_path = self.fsys.realpath(find_res.paths[0])
                analyse_path = self.fsys.realpath(find_res.analyse_path)

                assert dir_path == os.path.dirname(analyse_path)

                new_target = PackageTarget(symid,
                                           symtable,
                                           mbox,
                                           dir_path,
                                           analyse_path,
                                           mode=mode)
                new_target.module_temp = TypePackageTemp(
                    find_res.paths, new_target.symtable, new_target.symid)
                new_target.path = self.fsys.realpath(find_res.paths[0])

                self.__parse(new_target)
                self.update_stage(new_target, Stage.Preprocess)
                self.__add_target(new_target)

            elif find_res.res_type == ModuleFindRes.Namespace:
                assert False, "Namespace package not supported yet"

        return add_option

    def __add_target(self, target: Target):
        """Add target"""
        self.targets[target.symid] = target
        if target.path:
            self.fsys.add_path_symid_map(target.path, target.symid)

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

    def get_module_temp(self, symid: 'SymId') -> Optional[TypeModuleTemp]:
        if symid in self.targets:
            return self.targets[symid].module_temp
        return None

    def add_check_file(self, path: FilePath) -> Option[bool]:
        path = self.fsys.realpath(path)

        if not os.path.exists(path):
            add_option = Option(False)
            add_option.add_err(FileNotFound(path))
            return add_option
        else:
            rt_path = crawl_path(os.path.dirname(path))
            self.fsys.add_userpath(rt_path)
            symid = relpath2symid(rt_path, path)
            return self.__add_check_symid(symid, None, path)

    def add_check_symid(self, symid: 'SymId') -> Option[bool]:
        return self.__add_check_symid(symid)

    def add_check_target(self, target: 'Target'):
        assert target not in self.targets
        self.__add_target(target)
        self.update_stage(target, target.stage, True)

    def change_target_stage(self, target: 'Target', stage: Stage):
        assert target == self.targets.get(target.symid)
        self.update_stage(target, stage)

    def get_mbox_by_symid(self, symid: 'SymId') -> Optional[MessageBox]:
        target = self.targets.get(symid)
        if target:
            return target.mbox
        else:
            return None

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
        InferStarter(self.targets).start_infer()

    def get_sym_type(self, module_symid: SymId,
                     var_symid: SymId) -> Optional['TypeIns']:
        module_temp = self.get_module_temp(module_symid)
        if not module_temp:
            return None
        else:
            varid_list = symid2list(var_symid)
            cur_ins = module_temp.get_default_ins().value
            for subid in varid_list:
                res_option = cur_ins.getattribute(subid, None)
                if res_option.haserr():
                    return None
                cur_ins = res_option.value
            return cur_ins

    def eval_expr(self, module_symid: SymId, expr: str) -> Optional['TypeIns']:
        try:
            astnode = ast.parse(expr, mode='eval')
            module_temp = self.get_module_temp(module_symid)
            if not module_temp:
                return None
            module_ins = module_temp.get_default_ins().value
            res_option = eval_expr(astnode.body, module_ins)  # type: ignore
            if res_option.haserr():
                return None
            else:
                return res_option.value
        except SyntaxError as e:
            return None


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
