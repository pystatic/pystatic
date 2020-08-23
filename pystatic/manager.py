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

    # def update_imp_cache(self, item: ImpItem) -> ImpItem:
    #     self.imp_cache[item.uri] = item
    #     return item

    # def _dot_before_imp(self, to_imp: str) -> int:
    #     i = 0
    #     while len(to_imp) > i and to_imp[i] == '.':
    #         i += 1
    #     return i

    # def _find_through_path(self, to_imp: str,
    #                        cur_module: TypeModuleTemp) -> Optional[ImpItem]:
    #     dir_path = os.path.dirname(cur_module.path)
    #     i = self._dot_before_imp(to_imp)
    #     to_imp = to_imp[i:]
    #     while i >= 2:
    #         dir_path = os.path.dirname(dir_path)
    #         i -= 2

    #     imp_rel_path = os.path.sep.join(to_imp.split('.'))
    #     imp_path = os.path.join(dir_path, imp_rel_path)

    #     imp_uri = CHECKED_PACKET + imp_path
    #     if imp_uri in self.imp_cache:
    #         return self.imp_cache[imp_uri]

    #     # package?
    #     if os.path.isdir(imp_path):
    #         if os.path.isfile(os.path.join(imp_path, '__init__.py')):
    #             return self.update_imp_cache(
    #                 TypePackageTemp([imp_path], imp_uri))
    #         elif os.path.isfile(os.path.join(imp_path, '__init__.pyi')):
    #             return self.update_imp_cache(
    #                 TypePackageTemp([imp_path], imp_uri))
    #         else:
    #             return None
    #     else:
    #         if os.path.isfile(imp_path + '.pyi'):
    #             return self.semanal_module(imp_path + '.pyi', imp_uri)
    #         elif os.path.isfile(imp_path + '.py'):
    #             return self.semanal_module(imp_path + '.py', imp_uri)
    #         else:
    #             return None

    # def _get_imp_uri(self, to_imp: str,
    #                  cur_module: TypeModuleTemp) -> List[str]:
    #     i = self._dot_before_imp(to_imp)
    #     cur_module_uri = cur_module.exposed_pkg().split('.')
    #     if cur_module_uri[0] == '':
    #         cur_module_uri = []
    #     rel_uri = to_imp[i:].split('.')
    #     if i == 0:
    #         return cur_module_uri + rel_uri
    #     else:
    #         return cur_module_uri[:-(i // 2)] + rel_uri

    # def _search_type_file(self, uri: List[str], pathes: List[str],
    #                       start) -> List[str]:
    #     len_uri = len(uri)
    #     for i in range(start, len_uri):
    #         if not pathes:
    #             return []
    #         ns_pathes = []  # namespace packages
    #         target = None
    #         for path in pathes:
    #             sub_target = os.path.join(path, uri[i])

    #             if i == len_uri - 1:
    #                 pyi_file = sub_target + '.pyi'
    #                 py_file = sub_target + '.py'
    #                 if os.path.isfile(pyi_file):
    #                     return [pyi_file]
    #                 if os.path.isfile(py_file):
    #                     return [py_file]

    #             if os.path.isdir(sub_target):
    #                 init_file = os.path.join(sub_target, '__init__.py')
    #                 if os.path.isfile(init_file):
    #                     target = sub_target
    #                 else:
    #                     ns_pathes.append(sub_target)

    #         if target:
    #             pathes = [target]
    #         else:
    #             pathes = ns_pathes
    #     return pathes

    # def _find_through_uri(self, uri: List[str]) -> Optional[ImpItem]:
    #     def gen_impItem(pathes: List[str]):
    #         isdir = False
    #         for path in pathes:
    #             if not os.path.exists(path):
    #                 return None
    #             if os.path.isdir(path):
    #                 isdir = True
    #             elif isdir:
    #                 return None  # can't be package and module at the same time

    #         if isdir:  # package
    #             return TypePackageTemp(pathes, '.'.join(uri))
    #         else:
    #             assert len(pathes) == 1  # module
    #             return self.semanal_module(pathes[0], '.'.join(uri))

    #     # find under $MYPYPATH
    #     pathes = self._search_type_file(uri, self.config.manual_path, 0)
    #     if pathes:
    #         return gen_impItem(pathes)
    #     # find under cwd
    #     if self.config.mode == CheckMode.Package and uri[
    #             0] == self.config.package_name:
    #         pathes = self._search_type_file(uri, [self.config.cwd], 1)
    #     else:
    #         pathes = self._search_type_file(uri, [self.config.cwd], 0)
    #     if pathes:
    #         return gen_impItem(pathes)
    #     # find stub packages
    #     pathes = self._search_type_file(uri, self.config.sitepkg, 0)
    #     if pathes:
    #         return gen_impItem(pathes)
    #     # find typeshed
    #     return None

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
