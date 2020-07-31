from .env import Environment, Scope
from .typesys import float_type, int_type, str_type, bool_type, generic_type, none_type
from .fsys import File

builtin_scope = Scope(None, None, None, None)  # type: ignore
builtin_scope.glob = builtin_scope
builtin_scope.builtins = builtin_scope
builtin_scope.add_type('float', float_type)
builtin_scope.add_type('int', int_type)
builtin_scope.add_type('str', str_type)
builtin_scope.add_type('bool', bool_type)
builtin_scope.add_type('Generic', generic_type)
builtin_scope.add_type('float', float_type)
builtin_scope.add_type('None', none_type)


def get_init_env(module: File):
    """Return the default environment for a module

    Args:
        module: absolute path of the module
    """
    scope = Scope(None, None, None, None)  # type: ignore
    scope.glob = scope
    scope.builtins = builtin_scope

    return Environment(scope, module)
