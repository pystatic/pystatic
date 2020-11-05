import typing
from pystatic.symtable import SymTable, TableScope, Entry
from pystatic.arg import Argument, Arg
from pystatic.symid import SymId
from pystatic.typesys import *

builtin_symtable = SymTable('builtins', None, None, None, TableScope.GLOB)
builtin_symtable.glob = builtin_symtable
builtin_symtable.builtins = builtin_symtable

typing_symtable = SymTable('typings', None, None, None, TableScope.GLOB)
typing_symtable.glob = typing_symtable
typing_symtable.builtins = builtin_symtable


def add_spt_def(name, temp, ins=None):
    global typing_symtable
    typing_symtable._spt_types[name] = temp
    if ins:
        entry = Entry(ins)
    else:
        entry = Entry(temp.get_default_typetype())
    typing_symtable.add_entry(name, entry)


add_spt_def('Generic', generic_temp)
add_spt_def('Callable', callable_temp)
add_spt_def('Any', any_temp, any_type)
add_spt_def('Tuple', tuple_temp)
add_spt_def('Optional', optional_temp)
add_spt_def('Literal', literal_temp)
add_spt_def('Union', union_temp)
add_spt_def('TypeVar', typevar_temp, typevar_type)
add_spt_def('List', list_temp, list_type)
add_spt_def('Tuple', tuple_temp, tuple_type)


def get_builtin_symtable() -> SymTable:
    return builtin_symtable


def get_typing_symtable() -> SymTable:
    return typing_symtable


def get_init_module_symtable(symid: SymId) -> SymTable:
    new_symtable = SymTable(
        symid,
        None,  # type: ignore
        None,
        builtin_symtable,
        TableScope.GLOB)
    new_symtable.glob = new_symtable
    return new_symtable


def init_builtins(self):
    pass


def init_typeshed(self):
    pass
