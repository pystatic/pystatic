import os
import ast
import logging
from typing import Optional, List, TextIO
from pystatic.typesys import ImpItem, TypeModuleTemp, CHECKED_PACKET, TypeTemp
from pystatic.config import Config
from pystatic.env import get_init_env
from pystatic.semanal_main import ClassCollector, TypeRecorder
from pystatic.error import ErrHandler
from pystatic.module_cache import ModuleCache


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

        self.stdout = stdout
        self.stderr = stderr

        self.module_cache = ModuleCache(self)

    def deal_import(self, to_imp: str,
                    cur_module: ImpItem) -> Optional[TypeTemp]:
        return self.module_cache.lookup_from_module(to_imp, cur_module)

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
            module_name = os.path.splitext(os.path.basename(path))[0]
            self.semanal_module(path, CHECKED_PACKET + '.' + module_name)
