import os
import ast
import logging
from collections import deque
from pystatic.message import MessageBox
from typing import Optional, List, TextIO, Set, Dict, Deque
from pystatic.preprocess import Preprocessor
from pystatic.predefined import (get_builtin_symtable, get_typing_symtable,
                                 get_init_symtable)
from pystatic.symtable import SymTable
from pystatic.typesys import TypeModuleTemp, TpState
from pystatic.config import Config
from pystatic.modfinder import ModuleFinder
from pystatic.uri import Uri, relpath2uri
from pystatic.target import Target, Stage

logger = logging.getLogger(__name__)


class Manager:
    def __init__(self, config, module_files: List[str],
                 package_files: List[str], stdout: TextIO, stderr: TextIO):
        self.check_targets: Dict[Uri, Target] = {}

        self.config = Config(config)

        self.user_path: Set[str] = set()
        self.set_user_path(module_files)
        self.set_user_path(package_files)
        finder = ModuleFinder(self.config.manual_path, list(self.user_path),
                              self.config.sitepkg, self.config.typeshed,
                              self.config.python_version)
        self.preprocessor = Preprocessor(self, finder)

        self.stdout = stdout
        self.stderr = stderr

        self.find_check_files(module_files)
        self.find_check_files(package_files)

        self.mbox = MessageBox('test')  # TODO: refactor this

        self.init_typeshed()

    def init_typeshed(self):
        builtins_target = Target('builtins', get_builtin_symtable())
        typing_target = Target('typing', get_typing_symtable())
        self.preprocess([typing_target, builtins_target])

    def start_check(self):
        self.preprocess(list(self.check_targets.values()))
        for err in self.mbox.error:
            print(err)

    def preprocess(self, targets):
        self.preprocessor.process_module(targets)

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
            uri = relpath2uri(rt_path, srcfile)
            target = Target(uri, get_init_symtable(), stage=Stage.PreParse)
            self.check_targets[uri] = target


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
