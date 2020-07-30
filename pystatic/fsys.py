import os
from typing import Optional


class File(object):
    def __init__(self, path: str):
        assert os.path.isabs(path)
        self.abs_path = path
        self.dirname = os.path.dirname(path)

    def __eq__(self, other) -> bool:
        return other.abs_path == self.abs_path

    def __hash__(self) -> int:
        return hash(self.abs_path)


class ModuleResolution(object):
    """PEP 561

    - Stubs or Python source manually put in the beginning of the path.
    - User code - the files the type checker is running on.
    - Stub packages.
    - Inline packages.
    - Typeshed.
    """
    def __init__(self, pwd: str):
        self.pwd = pwd

    def resolve(self, module: str, file: File) -> Optional[File]:
        dirs = []

        if module.startswith('..'):
            dirs.append(os.path.dirname(file.dirname))
            rel_path = os.sep.join(module[2:].split('.'))
        elif module.startswith('.'):
            dirs.append(file.dirname)
            rel_path = os.sep.join(module[1:].split('.'))
        else:
            dirs.append(file.dirname)
            rel_path = os.sep.join(module.split('.'))

        for dir in dirs:
            path = os.path.join(dir, rel_path) + '.py'
            print(path)
            if os.path.isfile(path):
                return File(path)
        return None
