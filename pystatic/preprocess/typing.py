import ast
import enum
from typing import Optional, Union, TYPE_CHECKING
from pystatic.util import liter_unparse, LiterUnParseException

if TYPE_CHECKING:
    from pystatic.env import Environment


class SType(enum.Enum):
    """Special types

    TypeVar, TypeAlias...
    """
    TypeVar = 1
    TypeAlias = 2


def is_special_typing(
        node: Union[ast.Assign, ast.AnnAssign]) -> Optional[SType]:
    if isinstance(node.value, ast.Call):
        if isinstance(node.value.func, ast.Name):
            fname = node.value.func.id
            if fname == 'TypeVar':
                return SType.TypeVar
    return None


def analyse_special_typing(kind: SType, node: ast.AST, env: 'Environment'):
    # TODO: to impl
    pass


def analyse_typevar(node: ast.AST, env: 'Environment'):
    # TODO: to impl
    try:
        liter = liter_unparse(node)
    except LiterUnParseException as e:
        msg = e.msg or 'invalid syntax'
        env.add_err(e.node, msg)
