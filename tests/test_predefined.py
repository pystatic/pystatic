import ast
from pystatic.symtable import SymTable
import sys
import os

sys.path.extend(['.', '..'])

from pystatic.predefined import *
from pystatic.manager import Manager
from pystatic.config import Config


def test_predefined_type():
    builtin_symtable = get_builtin_symtable()
    typing_symtable = get_typing_symtable()
    config = Config({})
    manager = Manager(config)

    builtin_temp = manager.get_module_temp('builtins')
    typing_temp = manager.get_module_temp('typing')

    assert builtin_temp.get_inner_symtable() is builtin_symtable
    assert typing_temp.get_inner_symtable() is typing_symtable

    assert int_type is builtin_temp.getattribute('int', None)
    assert str_type is builtin_temp.getattribute('str', None)
    assert byte_type is builtin_temp.getattribute('byte', None)
    assert complex_type is builtin_temp.getattribute('complex', None)
    assert bool_type is builtin_temp.getattribute('bool', None)
    assert type_meta_ins is builtin_temp.getattribute('type', None)

    assert int_temp.getattribute('__add__', None)
    assert int_temp.getattribute('__sub__', None)

    assert typevar_type is typing_temp.getattribute('TypeVar', None)
