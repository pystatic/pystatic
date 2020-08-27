import ast
import enum
from typing import Optional, Union


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
