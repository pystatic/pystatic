import sys
import os
import enum
from typing import List, Optional, Set
from pystatic.sitepkg import get_sitepkg


class CheckMode(enum.Enum):
    Module = 1
    Package = 2


class Config:
    def __init__(self, config, targets: List[str]):
        if isinstance(config, dict):

            def get(attr: str):
                return config.get(attr)
        else:

            def get(attr: str):
                if hasattr(config, attr):
                    return getattr(config, attr)
                return None

        self.python_executable: str = get(
            'python_executable') or sys.executable

        self.mode: CheckMode = CheckMode.Package if get(
            'package') else CheckMode.Module
        self.package_directory: str = get('package_directory') or os.getcwd()
        self.package_name = os.path.basename(self.package_directory)

        # set cwd
        self.cwd: str
        if self.mode == CheckMode.Package:
            self.cwd = self.package_directory
        elif get('cwd'):
            cwd = get('cwd')
            self.cwd = os.path.abspath(cwd)  # type: ignore
        elif targets and os.path.exists(targets[0]):
            self.cwd = os.path.dirname(os.path.abspath(targets[0]))
        else:
            self.cwd = os.getcwd()

        self.manual_path: List[str] = get('manual_path') or []
        mypy_path = os.getenv('MYPYPATH')
        if mypy_path:
            for path in mypy_path.split(os.pathsep):
                if path not in self.manual_path:
                    self.manual_path.append(path)

        self.sitepkg: List[str] = get_sitepkg()

        self.typeshed: Optional[str] = None
