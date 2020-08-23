import os
import ast
import copy
import logging
from typing import ChainMap, Optional, Union, List, Dict, Set, TextIO
from pystatic.typesys import TypePackageTemp, TypeModuleTemp, TypeTemp, CheckedPacket
from pystatic.config import Config, CheckMode
from pystatic.env import get_init_env
from pystatic.semanal_main import ClassCollector, TypeRecorder
from pystatic.error import ErrHandler

ImpItem = Union[TypeModuleTemp, TypePackageTemp]


class Manager:
    def __init__(self, config, targets: List[str], stdout: TextIO,
                 stderr: TextIO):
        self.config = Config(config, targets)
        abs_targets = []
        for path in targets:
            if not os.path.isabs(path):
                path = os.path.normpath(os.path.join(self.config.cwd, path))
            if os.path.exists(path):
                abs_targets.append(path)

        self.targets = set(targets)
        self.config = Config(config, targets)

        self.imp_cache = {}

        self.stdout = stdout
        self.stderr = stderr

    def update_imp_cache(self, item: ImpItem) -> ImpItem:
        self.imp_cache[item.uri] = item
        return item

    def _find_through_path(self, to_imp: str,
                           cur_module: TypeModuleTemp) -> Optional[ImpItem]:
        dir_path = os.path.dirname(cur_module.path)
        i = 0
        while len(to_imp) > i and to_imp[i] == '.':
            i += 1
        to_imp = to_imp[i:]
        while i >= 2:
            dir_path = os.path.dirname(dir_path)
            i -= 2

        imp_rel_path = os.path.sep.join(to_imp.split('.'))
        imp_path = os.path.join(dir_path, imp_rel_path)

        imp_uri = CheckedPacket + imp_path
        if imp_uri in self.imp_cache:
            return self.imp_cache[imp_uri]

        # package?
        if os.path.isdir(imp_path):
            if os.path.isfile(os.path.join(imp_path, '__init__.py')):
                return self.update_imp_cache(TypePackageTemp(
                    imp_path, imp_uri))
            elif os.path.isfile(os.path.join(imp_path, '__init__.pyi')):
                return self.update_imp_cache(TypePackageTemp(
                    imp_path, imp_uri))
            else:
                return None
        else:
            if os.path.isfile(imp_path + '.pyi'):
                return self.semanal_module(imp_path + '.pyi', imp_uri)
            elif os.path.isfile(imp_path + '.py'):
                return self.semanal_module(imp_path + '.py', imp_uri)
            else:
                return None

    def import_find(self, to_imp: str,
                    cur_module: TypeModuleTemp) -> Optional[ImpItem]:
        """PEP 561

        - Stubs or Python source manually put at the beginning of the path($MYPYPATH)
        - User code - files the type checker is running on.
        - Stub packages.
        - Inline packages.
        - Typeshed.
        """
        if not to_imp:
            return None
        if to_imp[0] == '.' and cur_module.path.startswith(CheckedPacket):
            return self._find_through_path(to_imp, cur_module)
        else:
            return None  # TODO

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
        err = ErrHandler(tmp_tp_module.exposed_uri())
        ClassCollector(env, err, self).accept(treenode)
        TypeRecorder(env, err).accept(treenode)
        glob = env.glob_scope

        # output errors(only for debug)
        for e in err:
            self.stdout.write(str(e) + '\n')

        return TypeModuleTemp(path, uri, glob.types, glob.local)

    def check(self):
        for path in self.targets:
            self.semanal_module(path, CheckedPacket + path)
