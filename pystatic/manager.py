import os
import ast
import logging
import enum
from typing import Optional, List, TextIO, Set
from pystatic.typesys import ImpItem, TypeModuleTemp, TypePackageTemp, TypeTemp
from pystatic.config import Config
from pystatic.env import get_init_env
from pystatic.semanal_main import ClassCollector, TypeRecorder
from pystatic.error import ErrHandler
from pystatic.module_finder import ModuleFinder


class CheckMode(enum.Enum):
    Module = 1
    Package = 2


class CheckTarget:
    def __init__(self, src: str, uri: str, mode: CheckMode):
        self.src = src
        self.uri = uri
        self.mode = mode

    def __hash__(self):
        return hash(self.src)


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


class Manager:
    def __init__(self, config, module_files: List[str],
                 package_files: List[str], stdout: TextIO, stderr: TextIO):
        self.targets: Set[CheckTarget] = set()
        self.user_path = set()
        self.generate_targets(module_files, CheckMode.Module)
        self.generate_targets(package_files, CheckMode.Package)
        self.config = Config(config)
        self.finder = ModuleFinder(self.config.manual_path,
                                   list(self.user_path), self.config.sitepkg,
                                   self.config.typeshed, self)

        self.stdout = stdout
        self.stderr = stderr

    def generate_targets(self, srcfiles: List[str], mode: CheckMode):
        if mode == CheckMode.Module:
            for srcfile in srcfiles:
                srcfile = os.path.realpath(srcfile)
                if srcfile in self.targets or not os.path.exists(srcfile):
                    continue  # TODO: warning here
                rt_path = crawl_path(os.path.dirname(srcfile))
                uri = generate_uri(rt_path, srcfile)
                self.user_path.add(rt_path)
                self.targets.add(CheckTarget(srcfile, uri, CheckMode.Module))
        else:
            for srcfile in srcfiles:
                srcfile = os.path.realpath(srcfile)
                if srcfile in self.targets:
                    continue  # TODO: warning here
                if os.path.isdir(srcfile):
                    rt_path = os.path.dirname(srcfile)
                    self.user_path.add(rt_path)
                    self.targets.add(
                        CheckTarget(srcfile, os.path.basename(srcfile),
                                    CheckMode.Package))
                else:
                    pass  # TODO: warning here

    def deal_module_import(self, to_imp: str,
                           cur_module: TypeModuleTemp) -> Optional[TypeTemp]:
        if not to_imp:
            return None
        return self.finder.find_from_module(to_imp, cur_module)

    def deal_package_import(
            self, to_imp: str,
            cur_package: TypePackageTemp) -> Optional[TypeTemp]:
        if not to_imp:
            return None
        return self.finder.find_from_package(to_imp, cur_package)

    def semanal_module(self, path: str, uri: str) -> Optional[TypeModuleTemp]:
        try:
            with open(path) as f:
                src = f.read()
            treenode = ast.parse(src, type_comments=True)
        except SyntaxError as e:
            logging.debug(f'failed to parse {path}')
            return None
        except FileNotFoundError as e:
            logging.debug(f'{path} not found')
            return None
        tmp_tp_module = TypeModuleTemp(path, uri, {}, {})
        env = get_init_env(tmp_tp_module)
        err = ErrHandler(tmp_tp_module.uri)
        ClassCollector(env, err, self).accept(treenode)
        TypeRecorder(env, err).accept(treenode)
        glob = env.glob_scope

        # output errors(only for debug)
        for e in err:
            self.stdout.write(str(e) + '\n')

        return TypeModuleTemp(path, uri, glob.types, glob.local)

    def check(self):
        for target in self.targets:
            logging.info(f'Check {target.uri} {target.src}')
            self.semanal_module(target.src, target.uri)
