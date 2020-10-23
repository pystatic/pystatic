import os
import logging
from pystatic.message import MessageBox
from typing import Optional, List, TextIO, Set, Dict
from pystatic.preprocess import Preprocessor
from pystatic.predefined import (get_builtin_symtable, get_typing_symtable,
                                 get_init_module_symtable)
from pystatic.config import Config
from pystatic.modfinder import ModuleFinder
from pystatic.symid import SymId, relpath2symid
from pystatic.target import Target, Stage
from pystatic.infer.infer import InferStarter
from pystatic.stubgen import stubgen

logger = logging.getLogger(__name__)


class Manager:
    def __init__(self, config, module_files: List[str],
                 package_files: List[str], stdout: TextIO, stderr: TextIO,
                 load_typeshed: bool):
        self.check_targets: Dict[SymId, Target] = {}

        self.config = Config(config)

        self.user_path: Set[str] = set()
        self.set_user_path(module_files)
        self.set_user_path(package_files)
        finder = ModuleFinder(self.config.manual_path, list(self.user_path),
                              self.config.sitepkg, self.config.typeshed,
                              self.config.python_version)
        self.boxdict: Dict[str, MessageBox] = {}
        self.pre_proc = Preprocessor(self.boxdict, finder)

        self.stdout = stdout
        self.stderr = stderr

        self.find_check_files(module_files)
        self.find_check_files(package_files)

        if load_typeshed:
            self.init_typeshed()

    def init_typeshed(self):
        builtins_target = Target('builtins', get_builtin_symtable())
        typing_target = Target('typing', get_typing_symtable())
        self.preprocess([typing_target, builtins_target])

    def stubgen(self, rt_dir: Optional[str] = None):
        check_list = list(self.check_targets.values())
        self.preprocess(check_list)
        if rt_dir:
            stubgen(check_list, rt_dir)
        else:
            stubgen(check_list)

    def start_check(self):
        self.preprocess(list(self.check_targets.values()))
        self.start_infer()
        for key in self.boxdict.keys():
            self.boxdict[key].report()

    def start_infer(self):
        InferStarter(self.check_targets).start_infer()

    def preprocess(self, targets):
        self.pre_proc.process_module(targets)

    def set_user_path(self, srcfiles: List[str]):
        """Set user path according to sources"""
        for srcfile in srcfiles:
            srcfile = os.path.realpath(srcfile)
            if not os.path.exists(srcfile):
                logger.warning(f"{srcfile} doesn't exist")
                continue
            rt_path = crawl_path(os.path.dirname(srcfile))
            if rt_path not in self.user_path:
                self.user_path.add(rt_path)
                logger.debug(f'Add user path: {rt_path}')

    def find_check_files(self, srcfiles: List[str]):
        """Generate Target to be checked according to the srcfiles"""
        for srcfile in srcfiles:
            srcfile = os.path.realpath(srcfile)
            if not os.path.exists(srcfile):
                # already warned in set_user_path
                continue
            rt_path = crawl_path(os.path.dirname(srcfile))
            symid = relpath2symid(rt_path, srcfile)
            target = Target(symid,
                            get_init_module_symtable(symid),
                            path=srcfile,
                            stage=Stage.PreParse)
            self.set_target_mbox(target)
            self.check_targets[symid] = target

    def set_target_mbox(self, target: Target):
        """Set correct mbox according to a target"""
        if not target.mbox:
            target.mbox = MessageBox(target.symid)

        if target.path not in self.boxdict:
            self.boxdict[target.path] = target.mbox


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
