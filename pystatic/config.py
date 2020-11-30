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

        # cwd: current working direcotry
        # default: return value of os.getcwd()
        self.cwd: str = get('cwd', str) or os.getcwd()

        # manual_path: paths specified by user that pystatic will search for.
        # default: []
        self.manual_path: List[str] = get('manual_path') or []
        mypy_path = os.getenv('MYPYPATH')
        if mypy_path:
            for path in mypy_path.split(os.pathsep):
                if path not in self.manual_path:
                    self.manual_path.append(path)

        # sitepkg: sitepkg path
        self.sitepkg: List[str] = get_sitepkg()

        # typeshed: typeshed path
        # default: typeshed variable in this module
        if user_typeshed := get('typeshed', str):
            self.typeshed: Optional[str] = user_typeshed
        else:
            if os.path.isdir(os.path.join(pystatic_dir, typeshed)):
                self.typeshed = os.path.join(pystatic_dir, typeshed)
            else:
                self.typeshed = None
        
        if get('test_typeshed', bool):
            self.typeshed = os.path.join(pystatic_dir, 'typeshed')

        # no_typeshed: if true, then typeshed is not automatically loaded.
        # default: False.
        self.no_typeshed: bool = get('no_typeshed') or False
