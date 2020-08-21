import os
import ast
from typing import Optional


class File(object):
    def __init__(self, path: str):
        """ path must be an absolute path """
        assert os.path.isabs(path)
        self.abs_path = path
        self.mtime = -1

    @property
    def abs_path(self):
        """ absolute path """
        return self._abs_path

    @abs_path.setter
    def abs_path(self, path: str):
        self._abs_path = path
        self._update()

    def _update(self):
        self.dirname = os.path.dirname(self._abs_path)
        self.filename = os.path.basename(self._abs_path)
        if self.filename.endswith('.py'):
            self.module_name = self.filename[:-3]
        elif self.filename.endswith('.pyi'):
            self.module_name = self.filename[:-4]
        else:
            self.module_name = self.filename

    def isdir(self) -> bool:
        return os.path.isdir(self._abs_path)

    def _read(self) -> str:
        with open(self._abs_path) as f:
            self._content = f.read()
            return self._content

    def read(self) -> str:
        mtime = os.path.getmtime(self._abs_path)
        if mtime != self.mtime:
            self.mtime = mtime
            return self._read()
        else:
            return self._content

    def _parse(self) -> ast.AST:
        content = self._read()
        self._parse_tree = ast.parse(content, type_comments=True)
        return self._parse_tree

    def parse(self) -> ast.AST:
        mtime = os.path.getmtime(self._abs_path)
        if mtime != self.mtime:
            self.mtime = mtime
            return self._parse()
        else:
            return self._parse_tree

    def __eq__(self, other) -> bool:
        return other.abs_path == self.abs_path

    def __hash__(self) -> int:
        return hash(self.abs_path)


pwd = os.path.dirname(__file__)
typeshed = pwd
"""PEP 561

- Stubs or Python source manually put at the beginning of the path.
- User code - files the type checker is running on.
- Stub packages.
- Inline packages.
- Typeshed.
"""


def find_module(module: str, file: File) -> Optional[File]:
    dirs = []

    if module.startswith('..'):
        dirs.append(os.path.dirname(file.dirname))
        rel_path = os.sep.join(module[2:].split('.'))
    elif module.startswith('.'):
        dirs.append(file.dirname)
        rel_path = os.sep.join(module[1:].split('.'))
    else:
        rel_path = os.sep.join(module.split('.'))

    dirs.append(pwd)

    for dir in dirs:
        path = os.path.join(dir, rel_path)
        if os.path.isdir(path):
            init_path = os.path.join(path, '__init__.py')
            if os.path.isfile(init_path):
                return File(path)
        else:
            path = os.path.join(dir, rel_path) + '.py'
            if os.path.isfile(path):
                return File(path)
    return None
