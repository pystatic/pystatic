# https://docs.python.org/3/library/operator.html

import ast
from typing import Type, Dict, Tuple


def get_funname(op: Type):
    return op_map[op][0]


def get_opstr(op: Type):
    return op_map[op][1]


op_map: Dict[Type, Tuple[str, str]] = {
    ast.Lt: ("__lt__", "<"),
    ast.LtE: ("__le__", "<="),
    ast.Eq: ("__eq__", "=="),
    ast.NotEq: ("__ne__", "!="),
    ast.Gt: ("__gt__", ">"),
    ast.GtE: ("__ge__", ">="),
    ast.Not: ("__not__", "!"),
    ast.Add: ("__add__", "+"),
    ast.And: ("__and__", "&"),
    ast.FloorDiv: ("__floordiv__", "//"),
    ast.Invert: ("__invert__", "~"),
    ast.Mod: ("__mod__", "%"),
    ast.Mult: ("__mul__", "*"),
    ast.MatMult: ("__matmul__", "@"),
    ast.Or: ("__or__", "|"),
    ast.Sub: ("__sub__", "-"),
    ast.BitXor: ("__xor__", "^"),
    ast.LShift: ("__lshift__", "<<"),
    ast.RShift: ("__rshift__", ">>"),
    ast.USub: ("__neg__", "-"),
    ast.In: ("__contains__", "in"),
    ast.BitOr: ("__or__", "|")
}