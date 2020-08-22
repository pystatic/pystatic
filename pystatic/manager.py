import os
import ast
import copy
from io import TextIO
from typing import ChainMap, Optional, Union, List, Dict, Set
from pystatic.typesys import TypePackageTemp, TypeModuleTemp, TypeTemp
from pystatic.config import Config, CheckMode
from pystatic.typesys import CheckedPacket

# class File(object):
#     def __init__(self, path: str):
#         """ path must be an absolute path """
#         assert os.path.isabs(path)
#         self.abs_path = path
#         self.mtime = -1

#     @property
#     def abs_path(self):
#         """ absolute path """
#         return self._abs_path

#     @abs_path.setter
#     def abs_path(self, path: str):
#         self._abs_path = path
#         self._update()

#     def _update(self):
#         self.dirname = os.path.dirname(self._abs_path)
#         self.filename = os.path.basename(self._abs_path)
#         if self.filename.endswith('.py'):
#             self.module_name = self.filename[:-3]
#         elif self.filename.endswith('.pyi'):
#             self.module_name = self.filename[:-4]
#         else:
#             self.module_name = self.filename

#     def isdir(self) -> bool:
#         return os.path.isdir(self._abs_path)

#     def _read(self) -> str:
#         with open(self._abs_path) as f:
#             self._content = f.read()
#             return self._content

#     def read(self) -> str:
#         mtime = os.path.getmtime(self._abs_path)
#         if mtime != self.mtime:
#             self.mtime = mtime
#             return self._read()
#         else:
#             return self._content

#     def _parse(self) -> ast.AST:
#         content = self._read()
#         self._parse_tree = ast.parse(content, type_comments=True)
#         return self._parse_tree

#     def parse(self) -> ast.AST:
#         mtime = os.path.getmtime(self._abs_path)
#         if mtime != self.mtime:
#             self.mtime = mtime
#             return self._parse()
#         else:
#             return self._parse_tree

#     def __eq__(self, other) -> bool:
#         return other.abs_path == self.abs_path

#     def __hash__(self) -> int:
#         return hash(self.abs_path)

ImpItem = Union[TypeModuleTemp, TypePackageTemp]


class Manager:
    def __init__(self, config, targets: List[str], stdout: TextIO,
                 stderr: TextIO):
        self.config = Config(config, targets)
        self.targets = set(*targets)

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
                pass
            elif os.path.isfile(imp_path + '.py'):
                pass
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

    def check(self, file: str):
        pass