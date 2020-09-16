from pystatic.env import Environment
from pystatic.symtable import SymTable
from pystatic.typesys import (float_temp, int_temp, str_temp, bool_temp,
                              generic_temp, none_temp, any_temp, dummy_temp,
                              callable_temp)

builtin_symtable = SymTable(None, None, None, None)  # type: ignore
builtin_symtable.glob = builtin_symtable
builtin_symtable.builtins = builtin_symtable

builtin_symtable.add_entry('float', float_temp.get_default_type())
builtin_symtable.add_entry('int', int_temp.get_default_type())
builtin_symtable.add_entry('str', str_temp.get_default_type())
builtin_symtable.add_entry('bool', bool_temp.get_default_type())
builtin_symtable.add_entry('Generic', generic_temp.get_default_type())
builtin_symtable.add_entry('Callable', callable_temp.get_default_type())

builtin_symtable.add_entry('dummy', dummy_temp.get_default_type())


def get_init_env():
    return Environment(builtin_symtable)
