import os
import ast
import logging
import enum
from typing import Optional, List, TextIO, Set, Dict
from pystatic.typesys import TypeModuleTemp, TypePackageTemp
from pystatic.config import Config
from pystatic.preprocess.preprocess import (collect_type_def, import_type_def,
                                            bind_type_name)
from pystatic.modfinder import (ModuleFinder, ModuleFindRes)
from pystatic.env import Environment
from pystatic.moduri import ModUri, relpath2uri, uri2list

logger = logging.getLogger(__name__)


class ReadNsAst(Exception):
    pass


class Stage(enum.IntEnum):
    """Number ascends as the analysis going deeper"""
    Parse = 0
    Symtable = 1
    Deffer = 2
    Check = 4


class Target:
    def __init__(self, uri: ModUri, stage: Stage = Stage.Parse):
        self.uri = uri
        self.stage = stage

        self.ast: Optional[ast.AST] = None


class Manager:
    def __init__(self, config, module_files: List[str],
                 package_files: List[str], stdout: TextIO, stderr: TextIO):
        # Modules that need to check
        self.check_targets: Set[Target] = set()

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

        self.get_check_targets(module_files)
        self.get_check_targets(package_files)

    def start_check(self):
        pass

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

    def get_check_targets(self, srcfiles: List[str]):
        """Generate Target to be checked according to the srcfiles"""
        for srcfile in srcfiles:
            srcfile = os.path.realpath(srcfile)
            if not os.path.exists(srcfile):
                # already warned in set_user_path
                continue
            rt_path = crawl_path(os.path.dirname(srcfile))
            uri = relpath2uri(rt_path, srcfile)
            target = Target(uri, Stage.Parse)
            self.parse(target)
            self.check_targets.add(target)

    def parse(self, target: Target) -> ast.AST:
        assert target.stage == Stage.Parse
        target.ast = self.uri2ast(target.uri)
        return target.ast

    def uri2ast(self, uri: ModUri) -> ast.AST:
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
