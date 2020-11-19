import sys
import os
import pytest

sys.path.extend(['.', '..'])

from pystatic.typesys import TypeIns, TypeType
from pystatic.predefined import TypeModuleTemp, TypeFuncIns, TypeVarIns
from pystatic.config import Config
from pystatic.manager import Manager
from pystatic.typesys import TypeIns, TypeType
from pystatic.predefined import *
from pystatic.config import Config
from pystatic.manager import Manager
from pystatic.exprparse import eval_expr


@pytest.fixture
def init():
    config = Config({})
    manager = Manager(config)
    yield manager


def test_init_typevar(init):
    typevar = typing_symtable.lookup_local('TypeVar')
    assert typevar

    _name = typevar.getattribute('__name__', None).value
    _bound = typevar.getattribute('__bound__', None).value
    _constraints = typevar.getattribute('__constraints__', None).value
    _covariant = typevar.getattribute('__covariant__', None).value
    _contravariant = typevar.getattribute('__contravariant__', None).value

    _bound_type = TypeIns(optional_temp, [any_type])
    _constraints_type = TypeIns(tuple_temp, [any_type, ellipsis_ins])
    assert _name is str_ins
    assert _covariant is bool_ins
    assert _contravariant is bool_ins
    assert _bound.equiv(_bound_type)
    assert _constraints.equiv(_constraints_type)
