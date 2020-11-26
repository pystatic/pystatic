import ast
from typing import TYPE_CHECKING
from pystatic.reach import (Reach, cal_neg, is_true)
from pystatic.visitor import val_unparse, VisitException

if TYPE_CHECKING:
    from pystatic.config import Config


def is_accessible(test: 'ast.expr', config: 'Config'):
    res = static_infer(test, config)
    if res != Reach.UNKNOWN:
        setattr(test, 'reach', res)
    return is_true(res)


def static_infer(test: ast.expr, config: 'Config') -> Reach:
    if isinstance(test, ast.UnaryOp):
        res = static_infer(test.operand, config)
        op = test.op
        if isinstance(op, ast.Not):
            return cal_neg(res)
        elif isinstance(op, ast.UAdd):
            return res
        elif isinstance(op, ast.USub):
            if isinstance(test.operand, ast.Constant):  # -1 1 0 -0
                return res
            else:  # -False -True
                return cal_neg(res)
    elif isinstance(test, ast.BoolOp):
        if isinstance(test.op, ast.And):
            for value in test.values:
                value_reach = static_infer(value, config)
                if value_reach == Reach.ALWAYS_FALSE:
                    return Reach.ALWAYS_FALSE
                elif value_reach == Reach.UNKNOWN:
                    return Reach.UNKNOWN
        elif isinstance(test.op, ast.Or):
            for value in test.values:
                value_reach = static_infer(value, config)
                if value_reach == Reach.ALWAYS_TRUE:
                    return Reach.ALWAYS_TRUE
                elif value_reach == Reach.UNKNOWN:
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
    elif isinstance(test, ast.Name):
        if test.id == "TYPE_CHECKING":
            return Reach.TYPE_TRUE
    elif isinstance(test, ast.Constant):
        if test.value:
            return Reach.ALWAYS_TRUE
        else:
            return Reach.ALWAYS_FALSE
    return Reach.UNKNOWN


def is_cmp_python_version(node: ast.expr):
    if (isinstance(node, ast.Attribute) and node.attr == 'version_info'
            and isinstance(node.value, ast.Name) and node.value.id == 'sys'):
        return True
    else:
        return False


def cmp_by_op(left, right, op: ast.cmpop) -> Reach:
    cond_map = {False: Reach.ALWAYS_FALSE, True: Reach.ALWAYS_TRUE}
    try:
        if isinstance(op, ast.Eq):
            return cond_map[left == right]
        elif isinstance(op, ast.Gt):
            return cond_map[left > right]
        elif isinstance(op, ast.GtE):
            return cond_map[left >= right]
        elif isinstance(op, ast.Lt):
            return cond_map[left < right]
        elif isinstance(op, ast.LtE):
            return cond_map[left <= right]
        else:
            return Reach.UNKNOWN
    except TypeError:
        return Reach.UNKNOWN


def compare_python_version(sys_node: ast.expr,
                           cmp_node: ast.expr,
                           op: ast.cmpop,
                           config: 'Config',
                           atright=False) -> Reach:
    py_version = config.python_version
    try:
        right = val_unparse(cmp_node)
    except VisitException:
        return Reach.UNKNOWN
    if not isinstance(right, tuple):
        return Reach.UNKNOWN

    left = py_version
    if atright:
        left, right = right, left
    return cmp_by_op(left, right, op)
