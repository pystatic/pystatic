import ast
from typing import Type, Dict

# MGF: magic function
MGF_UADD = '__pos__'
MGF_USUB = '__neg__'
MGF_INVERT = '__invert__'
MGF_MULT = '__mul__'
MGF_ADD = '__add__'
MGF_SUB = '__sub__'

unaryop_map: Dict[Type, str] = {
    ast.UAdd: MGF_UADD,
    ast.USub: MGF_USUB,
    ast.Invert: MGF_INVERT,
}

binop_map: Dict[Type, str] = {
    ast.Add: MGF_ADD,
    ast.Sub: MGF_SUB,
    ast.Mult: MGF_MULT,
}

binop_char_map: Dict[Type, str] = {
    ast.Add: '+',
    ast.Sub: '-',
    ast.Mult: '*',
    ast.MatMult: '@',
    ast.Div: '/',
    ast.Mod: '%',
    ast.Pow: '**',
    ast.LShift: '<<',
    ast.RShift: '>>',
    ast.BitOr: '|',
    ast.BitXor: '^',
    ast.BitAnd: '&',
    ast.FloorDiv: '//'
}
