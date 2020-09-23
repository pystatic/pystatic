import os
import ast
import logging
import enum
from collections import deque
from pystatic.symtable import SymTable
from pystatic.message import MessageBox
from typing import Optional, List, TextIO, Set, Dict, Union, Deque
from pystatic import preprocess
from pystatic.typesys import TypeModuleTemp, TypePackageTemp
from pystatic.config import Config
from pystatic.modfinder import (ModuleFinder, ModuleFindRes)
from pystatic.env import Environment
from pystatic.uri import Uri, relpath2uri, uri2list

logger = logging.getLogger(__name__)


class ReadNsAst(Exception):
    pass


class Stage(enum.IntEnum):
    """Number ascends as the analysis going deeper"""
    PreParse = 0
    PreSymtable = 1
    Deffer = 2
    Check = 4


class Target:
    def __init__(self, uri: Uri, stage: Stage = Stage.PreParse):
        self.uri = uri
        self.stage = stage

        self.symtable = preprocess.get_init_env(
        ).symtable  # TODO: refactor this
        self.ast: Optional[ast.AST] = None

        self.module_temp = TypeModuleTemp(uri, self.symtable)


class Manager:
    def __init__(self, config, module_files: List[str],
                 package_files: List[str], stdout: TextIO, stderr: TextIO):
        self.check_targets: Dict[Uri, Target] = {}

        self.config = Config(config)

        self.user_path: Set[str] = set()
        self.set_user_path(module_files)
        self.set_user_path(package_files)
        self.finder = ModuleFinder(self.config.manual_path,
                                   list(self.user_path), self.config.sitepkg,
                                   self.config.typeshed,
                                   self.config.python_version)

        self.stdout = stdout
        self.stderr = stderr

        self.find_check_files(module_files)
        self.find_check_files(package_files)

        self.mbox = MessageBox('test')  # TODO: refactor this

        self.targets: Dict[Uri, Target] = {**self.check_targets}

        self.pre_queue: Deque[Target] = deque()

    def add_target(self, uri: Uri):
        if uri not in self.targets:
            new_target = Target(uri)
            self.targets[uri] = new_target
            self.pre_queue.append(new_target)

    def get_module_temp(self, uri: Uri) -> Optional[TypeModuleTemp]:
        if uri in self.targets:
            return self.targets[uri].module_temp
        else:
            return None

    def start_check(self):
        self.preprocess(list(self.check_targets.values()))

        for err in self.mbox.error:
            print(err)

    def preprocess(self, targets):
        if isinstance(targets, Target):
            self.pre_queue.append(targets)
        elif isinstance(targets, list):
            for target in targets:
                self.pre_queue.append(target)

        to_check: List[Target] = []
        while len(self.pre_queue) > 0:
            current = self.pre_queue[0]
            self.pre_queue.popleft()
            self.assert_parse(current)
            assert current.stage == Stage.PreSymtable
            assert current.ast
            to_check.append(current)

            preprocess.get_definition(current.ast, self, current.symtable,
                                      self.mbox, current.uri)

        for target in to_check:
            preprocess.resolve_import_type(target.symtable, self)

        preprocess.resolve_cls_def(to_check)

        for target in to_check:
            preprocess.resolve_typeins(target.symtable)

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
            target = Target(uri, Stage.PreParse)
            self.parse(target)
            self.check_targets[uri] = target

    def assert_parse(self, target: Target):
        if target.stage <= Stage.PreParse:
            self.parse(target)

    def parse(self, target: Target) -> ast.AST:
        # TODO: error handling
        assert target.stage == Stage.PreParse
        target.ast = self.uri2ast(target.uri)
        target.stage = Stage.PreSymtable
        return target.ast

    def is_valid_uri(self, uri: Uri) -> bool:
        find_res = self.finder.find(uri)
        if find_res:
            return True
        else:
            return False

    def uri2ast(self, uri: Uri) -> ast.AST:
        """Return the ast tree corresponding to uri.

        May throw SyntaxError or FileNotFoundError or ReadNsAst exception.
        """
        find_res = self.finder.find(uri)
        if not find_res:
            raise FileNotFoundError
        if find_res.res_type == ModuleFindRes.Module:
            assert len(find_res.paths) == 1
            assert find_res.target_file
            return path2ast(find_res.target_file)
        elif find_res.res_type == ModuleFindRes.Package:
            assert len(find_res.paths) == 1
            assert find_res.target_file
            return path2ast(find_res.target_file)
        elif find_res.res_type == ModuleFindRes.Namespace:
            raise ReadNsAst()
        else:
            assert False


def path2ast(path: str) -> ast.AST:
    """May throw FileNotFoundError or SyntaxError"""
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
