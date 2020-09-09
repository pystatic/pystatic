from optparse import Option
import sys
import os
import inspect
from typing import List, Optional, Type, Tuple

from pkg_resources import require
from pystatic.sitepkg import get_sitepkg

PY_VERSION = Tuple[int, int]

pystatic_dir: str = os.path.dirname(__file__)


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

        self.python_version: PY_VERSION = (sys.version_info.major,
                                           sys.version_info.minor)

        # set cwd
        self.cwd = os.getcwd()

        self.manual_path: List[str] = get('manual_path') or []
        mypy_path = os.getenv('MYPYPATH')
        if mypy_path:
            for path in mypy_path.split(os.pathsep):
                if path not in self.manual_path:
                    self.manual_path.append(path)

        self.sitepkg: List[str] = get_sitepkg()

        if get('typeshed', str):
            self.typeshed: Optional[str] = get('typeshed')
        else:
            if os.path.isdir(os.path.join(pystatic_dir, 'typeshed')):
                self.typeshed = os.path.join(pystatic_dir, 'typeshed')
            else:
                self.typeshed = None
