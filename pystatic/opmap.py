import ast
import _ast
from typing import Type, Dict

# MGF: magic function
MGF_UADD = "__pos__"
MGF_USUB = "__neg__"
MGF_INVERT = "__invert__"
MGF_MULT = "__mul__"
MGF_ADD = "__add__"
MGF_SUB = "__sub__"
MGF_LT = "__lt__"
MGF_GT = "__gt__"
MGF_EQ = "__eq__"

op_map: Dict[Type, str] = {
    # unary part
    ast.UAdd: MGF_UADD,
    ast.USub: MGF_USUB,
    ast.Invert: MGF_INVERT,
    # binary part
    ast.Add: MGF_ADD,
    ast.Sub: MGF_SUB,
    ast.Mult: MGF_MULT,
    ast.Eq: MGF_EQ,
    ast.Lt: MGF_LT,
    ast.Gt: MGF_GT,
}

op_char_map: Dict[Type, str] = {
    ast.Add: "+",
    ast.Sub: "-",
    ast.Mult: "*",
    ast.MatMult: "@",
    ast.Div: "/",
    ast.Mod: "%",
    ast.Pow: "**",
    ast.LShift: "<<",
    ast.RShift: ">>",
    ast.BitOr: "|",
    ast.BitXor: "^",
    ast.BitAnd: "&",
    ast.FloorDiv: "//",
    ast.Eq: "==",
    ast.Lt: "<",
    ast.Gt: ">",
}
