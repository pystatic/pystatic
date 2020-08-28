import os
import ast
import logging
import enum
from typing import Optional, List, TextIO, Set, Dict
from pystatic.typesys import ImpItem, TypeModuleTemp, TypePackageTemp, TypeTemp
from pystatic.config import Config
from pystatic.env import get_init_env
from pystatic.preprocess.preprocess import (collect_type_def, import_type_def,
                                            generate_type_binding)
from pystatic.error import ErrHandler
from pystatic.module_finder import (ModuleFinder, ModuleFindRes)

logger = logging.getLogger(__name__)


class AnalysisMode(enum.Enum):
    Module = 1
    Package = 2


class AnalysisState(enum.IntEnum):
    """Number ascends as the analysis going deeper"""
    UnTouched = 1
    TypeCollected = 2
    Imported = 3
    Binded = 4
    Checked = 5


# TODO: add support for Package Mode (with -p attribute in the cmdline)
class AnalysisTarget:
    def __init__(self, src: str, uri: str, mode: AnalysisMode):
        self.src = src
        self.uri = uri
        self.mode = mode

        self.state = AnalysisState.UnTouched

    def __hash__(self):
        return hash(self.src)


class Manager:
    def __init__(self, config, module_files: List[str],
                 package_files: List[str], stdout: TextIO, stderr: TextIO):
        self.targets: Set[AnalysisTarget] = set()
        self.user_path: Set[str] = set()
        self.generate_targets(module_files, AnalysisMode.Module)
        self.generate_targets(package_files, AnalysisMode.Package)
        self.config = Config(config)
        self.finder = ModuleFinder(self.config.manual_path,
                                   list(self.user_path), self.config.sitepkg,
                                   self.config.typeshed)

        self.stdout = stdout
        self.stderr = stderr

        self.check_set: Dict[str, AnalysisTarget] = {}

    def check(self):
        for target in self.targets:
            logging.info(f'Check {target.uri} {target.src}')
            self.semanal_module(target.src, target.uri)

    def register(self, uri: str):
        pass

    def get_cached(self) -> Optional[AnalysisTarget]:
        return self.check_set.get()

    def generate_targets(self, srcfiles: List[str], mode: AnalysisMode):
        """Generate AnalysisTarget according to the srcfiles

        Set user_path at the same time.
        """
        if mode == AnalysisMode.Module:
            for srcfile in srcfiles:
                srcfile = os.path.realpath(srcfile)
                if srcfile in self.targets or not os.path.exists(srcfile):
                    continue  # TODO: warning here
                rt_path = crawl_path(os.path.dirname(srcfile))
                uri = generate_uri(rt_path, srcfile)
                self.user_path.add(rt_path)
                self.targets.add(
                    AnalysisTarget(srcfile, uri, AnalysisMode.Module))
        else:
            for srcfile in srcfiles:
                srcfile = os.path.realpath(srcfile)
                if srcfile in self.targets:
                    continue  # TODO: warning here
                if os.path.isdir(srcfile):
                    rt_path = os.path.dirname(srcfile)
                    self.user_path.add(rt_path)
                    self.targets.add(
                        AnalysisTarget(srcfile, os.path.basename(srcfile),
                                       AnalysisMode.Package))
                else:
                    pass  # TODO: warning here

    def deal_import(self, uri: str,
                    module: TypeModuleTemp) -> Optional[TypeTemp]:
        if not uri:
            return None

        find_res = self.finder.relative_find(uri, module)
        if find_res.res_type == ModuleFindRes.Module:
            pass
        elif find_res.res_type == ModuleFindRes.Package:
            pass
        elif find_res.res_type == ModuleFindRes.Namespace:
            pass
        else:
            return None

    def semanal_module(self, uri: str) -> Optional[TypeModuleTemp]:
        pass

    # def semanal_module(self, path: str, uri: str) -> Optional[TypeModuleTemp]:
    #     try:
    #         with open(path) as f:
    #             src = f.read()
    #         treenode = ast.parse(src, type_comments=True)
    #     except SyntaxError as e:
    #         logging.debug(f'failed to parse {path}')
    #         return None
    #     except FileNotFoundError as e:
    #         logging.debug(f'{path} not found')
    #         return None
    #     else:
    #         tmp_tp_module = TypeModuleTemp(path, uri, {}, {})
    #         env = get_init_env(tmp_tp_module)
    #         collect_type_def(treenode, env, self)
    #         import_type_def(treenode, env, self)
    #         generate_type_binding(treenode, env)
    #         glob = env.glob_scope

    #         # output errors(only for debug)
    #         for err in env.err:
    #             self.stdout.write(str(err) + '\n')

    #         return TypeModuleTemp(path, uri, glob.types, glob.local)


def crawl_path(path):
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


def generate_uri(prefix_path: str, src_path: str):
    commonpath = os.path.commonpath([prefix_path, src_path])
    relpath = os.path.relpath(src_path, commonpath)
    if relpath.endswith('.py'):
        relpath = relpath[:-3]
    elif relpath.endswith('.pyi'):
        relpath = relpath[:-4]
    return '.'.join(relpath.split(os.path.sep))
