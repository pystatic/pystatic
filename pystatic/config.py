import sys
import os
import inspect
from typing import List, Optional, Type, Tuple, Final

from pystatic.sitepkg import get_sitepkg

PY_VERSION = Tuple[int, int]

pystatic_dir: str = os.path.dirname(__file__)

typeshed: Final[str] = 'faketypeshed'


class Config:
    def __init__(self, config):
        def get(attr: str, require_type: Optional[Type] = None):
            if require_type:
                assert inspect.isclass(require_type)
            if isinstance(config, dict):
                res = config.get(attr)
            else:
                res = getattr(config, attr, None)

            if res:
                if not require_type or isinstance(res, require_type):
                    return res
                else:
                    return None
            return None

        # python_version
        self.python_version: PY_VERSION = (sys.version_info.major,
                                           sys.version_info.minor)

        # cwd
        self.cwd: str = get('cwd', str) or os.getcwd()

        # manual path
        self.manual_path: List[str] = get('manual_path') or []
        mypy_path = os.getenv('MYPYPATH')
        if mypy_path:
            for path in mypy_path.split(os.pathsep):
                if path not in self.manual_path:
                    self.manual_path.append(path)

        # sitepkg path
        self.sitepkg: List[str] = get_sitepkg()

        # typeshed path
        if get('typeshed', str):
            self.typeshed: Optional[str] = get('typeshed')
        else:
            if os.path.isdir(os.path.join(pystatic_dir, typeshed)):
                self.typeshed = os.path.join(pystatic_dir, typeshed)
            else:
                self.typeshed = None

        # load_typeshed
        self.load_typeshed: bool = get('load_typeshed') or False
