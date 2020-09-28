import typing
from pystatic.env import Environment
from pystatic.symtable import SymTable, TableScope, Entry
from pystatic.typesys import *

# int_temp = TypeClassTemp('int', TpState.OVER)
# float_temp = TypeClassTemp('float', TpState.OVER)
# complex_temp = TypeClassTemp('complex', TpState.OVER)
# str_temp = TypeClassTemp('str', TpState.OVER)
# bool_temp = TypeClassTemp('bool', TpState.OVER)
# func_temp = TypeClassTemp('function', TpState.OVER)

builtin_symtable = SymTable(None, None, None, TableScope.GLOB)  # type: ignore
builtin_symtable.glob = builtin_symtable
builtin_symtable.builtins = builtin_symtable

# builtin_symtable.add_entry('float', Entry(float_temp.get_default_type()))
# builtin_symtable.add_entry('int', Entry(int_temp.get_default_type()))
# builtin_symtable.add_entry('str', Entry(str_temp.get_default_type()))
# builtin_symtable.add_entry('bool', Entry(bool_temp.get_default_type()))
# builtin_symtable.add_entry('...', Entry(ellipsis_type))

typing_symtable = SymTable(None, None, None, TableScope.GLOB)  # type: ignore
typing_symtable.glob = typing_symtable
typing_symtable.builtins = builtin_symtable


def add_spt_def(name, temp, ins=None):
    global typing_symtable
    typing_symtable._spt_types[name] = temp
    if ins:
        entry = Entry(ins)
    else:
        entry = Entry(temp.get_default_type())
    typing_symtable.add_entry(name, entry)


add_spt_def('Generic', generic_temp)
add_spt_def('Callable', callable_temp)
add_spt_def('Any', any_temp, any_type)
add_spt_def('Tuple', tuple_temp)
add_spt_def('Optional', optional_temp)
add_spt_def('Literal', literal_temp)
add_spt_def('Union', union_temp)


def get_builtin_symtable() -> SymTable:
    return builtin_symtable


def get_typing_symtable() -> SymTable:
    return typing_symtable


def get_init_symtable() -> SymTable:
    new_symtable = SymTable(
        None,  # type: ignore
        None,
        builtin_symtable,
        TableScope.GLOB)
    return new_symtable
