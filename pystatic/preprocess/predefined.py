from pystatic.env import Environment
from pystatic.symtable import SymTable, Tabletype, Entry
from pystatic.typesys import (float_temp, int_temp, str_temp, bool_temp,
                              generic_temp, dummy_temp, callable_temp)

builtin_symtable = SymTable(None, None, None, Tabletype.GLOB)  # type: ignore
builtin_symtable.glob = builtin_symtable
builtin_symtable.builtins = builtin_symtable

builtin_symtable.add_entry('float', Entry(float_temp.get_default_type()))
builtin_symtable.add_entry('int', Entry(int_temp.get_default_type()))
builtin_symtable.add_entry('str', Entry(str_temp.get_default_type()))
builtin_symtable.add_entry('bool', Entry(bool_temp.get_default_type()))
builtin_symtable.add_entry('Generic', Entry(generic_temp.get_default_type()))
builtin_symtable.add_entry('Callable', Entry(callable_temp.get_default_type()))

builtin_symtable.add_entry('dummy', Entry(dummy_temp.get_default_type()))


def get_builtin_env() -> Environment:
    return Environment(builtin_symtable)


def get_init_env() -> Environment:
    new_symtable = SymTable(
        None,  # type: ignore
        None,
        builtin_symtable,
        Tabletype.GLOB)
    new_symtable.glob = new_symtable
    return Environment(new_symtable)
