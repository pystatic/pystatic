import sys
import os
from typing import List, Optional
from pystatic.sitepkg import get_sitepkg


class Config:
    def __init__(self, config):
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

        # set cwd
        self.cwd = os.getcwd()

        self.manual_path: List[str] = get('manual_path') or []
        mypy_path = os.getenv('MYPYPATH')
        if mypy_path:
            for path in mypy_path.split(os.pathsep):
                if path not in self.manual_path:
                    self.manual_path.append(path)

        self.sitepkg: List[str] = get_sitepkg()

        self.typeshed: Optional[List[str]] = None
