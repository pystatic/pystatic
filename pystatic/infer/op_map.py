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
