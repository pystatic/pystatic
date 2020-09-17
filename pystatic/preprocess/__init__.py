from typing import TYPE_CHECKING
from pystatic.preprocess.definition import DefVisitor
from pystatic.preprocess.defer import remove_defer
from pystatic.preprocess.predefined import get_builtin_env, get_init_env

if TYPE_CHECKING:
    import ast
    from pystatic.env import Environment
    from pystatic.message import MessageBox


def get_definition(ast: 'ast.AST', env: 'Environment', mbox: 'MessageBox'):
    return DefVisitor(env, mbox).accept(ast)
