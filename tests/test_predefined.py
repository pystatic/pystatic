import ast
import builtins
from pystatic.symtable import SymTable
import sys
import os

sys.path.extend(['.', '..'])

from pystatic.predefined import *
from pystatic.manager import Manager
from pystatic.config import Config


def test_predefined_type():
    config = Config({})
    manager = Manager(config)

    builtins_ins = manager.get_module_ins('builtins')
    typing_ins = manager.get_module_ins('typing')

    assert builtins_ins.get_inner_symtable() is builtins_symtable
    assert typing_ins.get_inner_symtable() and typing_symtable

    assert int_type is builtins_ins.getattribute('int', None).value
    assert str_type is builtins_ins.getattribute('str', None).value
    assert byte_type is builtins_ins.getattribute('byte', None).value
    assert complex_type is builtins_ins.getattribute('complex', None).value
    assert bool_type is builtins_ins.getattribute('bool', None).value
    assert type_meta_type is builtins_ins.getattribute('type', None).value

    assert int_temp.getattribute('__add__', None)
    assert int_temp.getattribute('__sub__', None)

    assert typevar_type is typing_ins.getattribute('TypeVar', None).value
