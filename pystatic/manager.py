import os
import logging
from collections import deque
from typing import Optional, Dict, TYPE_CHECKING
from pystatic.typesys import TypeModuleTemp, TypePackageTemp, TypeIns
from pystatic.message import MessageBox
from pystatic.preprocess import Preprocessor
from pystatic.predefined import (get_builtin_symtable, get_typing_symtable,
                                 get_init_module_symtable)
from pystatic.config import Config
from pystatic.fsys import Filesys, FilePath, ModuleFindRes
from pystatic.symid import SymId, relpath2symid, symid2list
from pystatic.target import BlockTarget, Target, Stage
from pystatic.infer.infer import InferStarter
from pystatic.option import Option
from pystatic.errorcode import *

if TYPE_CHECKING:
    from pystatic.symtable import SymTable

logger = logging.getLogger(__name__)


class Manager:
    def __init__(self, config: Config):
        self.config = config

        self.fsys = Filesys(config)

        self.pre_proc = Preprocessor(self)
        self.targets: Dict[str, Target] = {}

        self.q_preprocess = deque()
        self.q_infer = deque()

        if config.load_typeshed:
            self.__init_typeshed()

    def __init_typeshed(self):
        self.__add_check_symid('builtins', get_builtin_symtable())
        self.__add_check_symid('typing', get_typing_symtable())
        self.preprocess()

    def __add_check_symid(self,
                          symid: 'SymId',
                          default_symtable: Optional['SymTable'] = None,
                          oldpath: Optional[FilePath] = None) -> Option[bool]:
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
            assert find_res.target_file

            if oldpath and oldpath != find_res.paths[0]:
                # TODO: report name collision
                add_option = Option(False)
                return add_option

            new_target = Target(symid, symtable, mbox,
                                self.fsys.realpath(find_res.target_file))

            if find_res.res_type == ModuleFindRes.Module:
                self.__add_target(new_target, find_res.target_file)

            elif find_res.res_type == ModuleFindRes.Package:
                new_target.module_temp = TypePackageTemp(
                    find_res.paths, new_target.symtable, new_target.symid)
                new_target.path = self.fsys.realpath(find_res.paths[0])

                self.__add_target(new_target, find_res.target_file)

            elif find_res.res_type == ModuleFindRes.Namespace:
                assert False, "Namespace package not supported yet"

        return add_option

    def __add_target(self, target: Target, analyse_path: FilePath):
        """Add target.

        analyse_path:
            the path of the file to be analysed. If the target represents a
            package, then analyse_path is path of corresponding __init__.py file
            while target.path is the path of the package.
        
        """
        assert os.path.isabs(target.path)

        target.ast = path2ast(analyse_path)
        self.targets[target.symid] = target
        self.fsys.add_path_symid_map(target.path, target.symid)

        self.add_to_queue(target, Stage.Preprocess)

    def is_module(self, symid: 'SymId') -> bool:
        """symid represents a valid module?"""
        find_res = self.fsys.find_module(symid)
        if not find_res:
            return False
        else:
            return True

    def add_to_queue(self, target: BlockTarget, stage: Stage):
        if stage == Stage.Preprocess:
            target.stage = Stage.Preprocess
            self.q_preprocess.append(target)
        elif stage == Stage.Infer:
            target.stage = Stage.Infer
            self.q_infer.append(target)

    def get_module_temp(self, symid: 'SymId') -> Optional[TypeModuleTemp]:
        if symid in self.targets:
            return self.targets[symid].module_temp

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

    def get_mbox_by_symid(self, symid: 'SymId') -> Optional[MessageBox]:
        target = self.targets.get(symid)
        if target:
            return target.mbox
        else:
            return None

    def get_mbox(self, path: FilePath) -> Optional[MessageBox]:
        symid = self.fsys.path_to_symid(path)
        if symid:
            return self.get_mbox_by_symid(symid)
        return None

    def preprocess(self):
        self.pre_proc.process()
        pass

    def preprocess_block(self, blk_target: BlockTarget):
        self.add_to_queue(blk_target, Stage.Preprocess)
        self.pre_proc.process()
        pass

    def infer(self):
        self.preprocess()
        pass

    def get_sym_type(self, module_symid: SymId,
                     var_symid: SymId) -> Optional['TypeIns']:
        target = self.targets.get(module_symid)
        if target:
            varid_list = symid2list(var_symid)
            cur_ins = target.module_temp.get_default_ins().value
            for subid in varid_list:
                res_option = cur_ins.getattribute(subid, None)
                if res_option.haserr():
                    return None
                cur_ins = res_option.value
            return cur_ins
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
