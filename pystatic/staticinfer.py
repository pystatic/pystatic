import ast
from typing import TYPE_CHECKING
from pystatic.reach import (Reach, cal_neg, is_true)
from pystatic.visitor import val_unparse
from pystatic.util import ParseException

if TYPE_CHECKING:
    from pystatic.config import Config


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
        right = val_unparse(cmp_node)
    except ParseException:
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