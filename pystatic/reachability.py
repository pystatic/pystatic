from typing import Final, TYPE_CHECKING
import ast
import enum
from pystatic.util import unparse, UnParseException

if TYPE_CHECKING:
    from pystatic.config import Config


class Reach(enum.Enum):
    # always true when type checking
    TYPE_TRUE = 1  # type: Final
    # always false when type checking
    TYPE_FALSE = 2  # type: Final
    # always true runtime
    RUNTIME_TRUE = 3  # type: Final
    # always false runtime
    RUNTIME_FALSE = 4  # type: Final
    # always true
    ALWAYS_TRUE = 5  # type: Final
    # always false
    ALWAYS_FALSE = 6  # type: Final
    # unknown
    UNKNOWN = 7  # type: Final


def cal_neg(res: Reach) -> Reach:
    if res == Reach.TYPE_TRUE:
        return Reach.TYPE_FALSE
    elif res == Reach.TYPE_FALSE:
        return Reach.TYPE_TRUE
    elif res == Reach.RUNTIME_TRUE:
        return Reach.RUNTIME_FALSE
    elif res == Reach.RUNTIME_FALSE:
        return Reach.RUNTIME_TRUE
    elif res == Reach.ALWAYS_FALSE:
        return Reach.ALWAYS_TRUE
    elif res == Reach.ALWAYS_TRUE:
        return Reach.ALWAYS_FALSE
    else:
        return Reach.UNKNOWN


def is_true(res: Reach, runtime=False) -> bool:
    if runtime:
        return res in (Reach.ALWAYS_TRUE, Reach.RUNTIME_TRUE)
    else:
        return res in (Reach.ALWAYS_TRUE, Reach.TYPE_TRUE)


def infer_reachability_if(test: ast.expr, config: 'Config') -> Reach:
    if isinstance(test, ast.UnaryOp):
        res = infer_reachability_if(test.operand, config)
        return cal_neg(res)
    elif isinstance(test, ast.BinOp):
        left_res = infer_reachability_if(test.left, config)
        if isinstance(test.op, ast.And):
            if left_res == Reach.ALWAYS_TRUE:
                return infer_reachability_if(test.right, config)
            else:
                return left_res
        elif isinstance(test.op, ast.Or):
            if left_res == Reach.ALWAYS_TRUE:
                return Reach.ALWAYS_TRUE
            else:
                return infer_reachability_if(test.right, config)
        return Reach.UNKNOWN
    elif isinstance(test, ast.Compare):
        left = test.left
        for cmpa, op in zip(test.comparators, test.ops):
            right = cmpa
            if is_cmp_python_version(left):
                res = compare_python_version(left, right, op, config, False)
            elif is_cmp_python_version(right):
                res = compare_python_version(right, left, op, config, True)
            else:
                return Reach.UNKNOWN

            if not is_true(res, False):
                return res
            left = cmpa

        return Reach.ALWAYS_TRUE
    else:
        return Reach.UNKNOWN


def is_cmp_python_version(node: ast.expr):
    if (isinstance(node, ast.Attribute) and node.attr == 'version_info'
            and isinstance(node.value, ast.Name) and node.value.id == 'sys'):
        return True
    else:
        return False


def compare_python_version(sys_node: ast.expr,
                           cmp_node: ast.expr,
                           op: ast.cmpop,
                           config: 'Config',
                           atright=False) -> Reach:
    py_version = config.python_version
    try:
        right = unparse(cmp_node)
    except UnParseException:
        return Reach.UNKNOWN
    if not isinstance(right, tuple):
        return Reach.UNKNOWN

    left = py_version
    if atright:
        left, right = right, left
    if isinstance(op, ast.Eq):
        if not left == right:
            return Reach.ALWAYS_FALSE
    elif isinstance(op, ast.Gt):
        if not left > right:
            return Reach.ALWAYS_FALSE
    elif isinstance(op, ast.GtE):
        if not left >= right:
            return Reach.ALWAYS_FALSE
    elif isinstance(op, ast.Lt):
        if not left < right:
            return Reach.ALWAYS_FALSE
    elif isinstance(op, ast.LtE):
        if not left <= right:
            return Reach.ALWAYS_FALSE

    return Reach.ALWAYS_TRUE
