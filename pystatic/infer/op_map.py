import ast

unaryop_map = {
    ast.UAdd: "__pos__",
    ast.USub: "__neg__",
    ast.Invert: "__invert__",
}

binop_map = {
    ast.Add: "__add__",
    ast.Sub: "__sub__",
    ast.Mult: "__mul__",
}

cmpop_map = {
    ast.Gt: '>',
    ast.Lt: '<',
    ast.Eq: '==',
    ast.GtE: '>=',
    ast.LtE: '<=',
    ast.NotEq: '!=',
    ast.Is: 'is',
    ast.IsNot: 'is not',
    ast.In: 'in',
    ast.NotIn: 'not in'
}

binop_char_map = {
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
