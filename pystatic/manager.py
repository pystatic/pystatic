import os
import logging
from typing import Optional, Dict, TYPE_CHECKING
from pystatic.typesys import TypeModuleTemp, TypePackageTemp
from pystatic.message import MessageBox
from pystatic.preprocess import Preprocessor
from pystatic.predefined import (get_builtin_symtable, get_typing_symtable,
                                 get_init_module_symtable)
from pystatic.config import Config
from pystatic.fsys import ModuleFinder, FilePath, ModuleFindRes
from pystatic.symid import SymId, relpath2symid
from pystatic.target import Target, Stage
from pystatic.infer.infer import InferStarter
from pystatic.option import Option
from pystatic.errorcode import *

if TYPE_CHECKING:
    from pystatic.symtable import SymTable

logger = logging.getLogger(__name__)


class Manager:
    def __init__(self, config: Config):
        self.config = config

        self.module_finder = ModuleFinder(self.config.manual_path,
                                          self.config.sitepkg,
                                          self.config.typeshed,
                                          self.config.python_version)
        self.path_symid_map: Dict[FilePath, 'SymId'] = {}
        self.pre_proc = Preprocessor(self)
        self.targets: Dict[str, Target] = {}

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
        find_res = self.module_finder.find(symid)
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
                                os.path.realpath(find_res.target_file))

            if find_res.res_type == ModuleFindRes.Module:
                self.__add_target(new_target, find_res.target_file)

            elif find_res.res_type == ModuleFindRes.Package:
                new_target.module_temp = TypePackageTemp(
                    find_res.paths, new_target.symtable, new_target.symid)
                new_target.path = os.path.realpath(find_res.paths[0])

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
        target.stage = Stage.Preprocess
        self.targets[target.symid] = target
        self.path_symid_map[target.path] = target.symid

        self.pre_proc.add_to_process_queue(target)

    def is_module(self, symid: 'SymId') -> bool:
        """symid represents a valid module?"""
        find_res = self.module_finder.find(symid)
        if not find_res:
            return False
        else:
            return True

    def get_module_temp(self, symid: 'SymId') -> Optional[TypeModuleTemp]:
        if symid in self.targets:
            return self.targets[symid].module_temp

    def add_check_file(self, path: FilePath) -> Option[bool]:
        path = os.path.realpath(path)

        if not os.path.exists(path):
            add_option = Option(False)
            add_option.add_err(FileNotFound(path))
            return add_option
        else:
            rt_path = crawl_path(os.path.dirname(path))
            self.module_finder.add_userpath(rt_path)
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
        path = os.path.realpath(path)
        symid = self.path_symid_map.get(path, None)
        if symid:
            return self.get_mbox_by_symid(symid)
        return None

    def preprocess(self):
        self.pre_proc.process_module()
        pass

    def preprocess_block(self):
        pass


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
