from typing import List
from pystatic.preprocess.resolve_local import resolve_func, resolve_local
from pystatic.preprocess.resolve_cls import (resolve_cls, resolve_cls_method,
                                             resolve_cls_placeholder)
from pystatic.preprocess.resolve_impt import resolve_import
from pystatic.preprocess.resolve_spt import resolve_spt
from pystatic.preprocess.prepinfo import *


def resolve(prepdef_list: List['PrepDef']):
    for prepdef in prepdef_list:
        if isinstance(prepdef, prep_cls):
            resolve_cls(prepdef)
        elif isinstance(prepdef, prep_func):
            resolve_func(prepdef)
        elif isinstance(prepdef, prep_local):
            resolve_local(prepdef)
        else:
            raise TypeError()
