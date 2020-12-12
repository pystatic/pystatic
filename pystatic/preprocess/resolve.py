from pystatic.preprocess.resolve_local import resolve_local
from pystatic.preprocess.resolve_func import resolve_func
from pystatic.preprocess.resolve_cls import (
    resolve_cls,
    resolve_cls_method,
    resolve_cls_placeholder,
)
from pystatic.preprocess.resolve_impt import resolve_import
from pystatic.preprocess.resolve_spt import resolve_typealias, resolve_typevar
from pystatic.preprocess.prepinfo import *


def resolve(prepdef: PrepDef, shallow: bool):
    if prepdef.stage == PREP_COMPLETE:
        return
    if isinstance(prepdef, prep_local):
        resolve_local(prepdef, shallow)
    elif isinstance(prepdef, prep_cls):
        resolve_cls(prepdef, shallow)
    elif isinstance(prepdef, prep_func):
        if not shallow:
            resolve_func(prepdef)
    else:
        raise TypeError()
