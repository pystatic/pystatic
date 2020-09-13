from pystatic.env import Scope
from pystatic.typesys import (float_temp, int_temp, str_temp, bool_temp,
                              generic_temp, none_temp, any_temp)

builtin_scope = Scope(None, None, None, None)  # type: ignore
builtin_scope.glob = builtin_scope
builtin_scope.builtins = builtin_scope
builtin_scope.add_type('float', float_temp)
builtin_scope.add_type('int', int_temp)
builtin_scope.add_type('str', str_temp)
builtin_scope.add_type('bool', bool_temp)
builtin_scope.add_type('Generic', generic_temp)
builtin_scope.add_type('None', none_temp)
builtin_scope.add_type('Any', any_temp)

builtin_scope.add_var('float', float_temp.get_default_type())
builtin_scope.add_var('int', int_temp.get_default_type())
builtin_scope.add_var('str', str_temp.get_default_type())
builtin_scope.add_var('bool', bool_temp.get_default_type())
builtin_scope.add_var('Generic', generic_temp.get_default_type())
