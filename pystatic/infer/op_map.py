import ast

unaryop_map = {
    ast.UAdd: "__pos__",
    ast.USub: "__neg__",
    ast.Invert: "__invert__",
    # ast.Not: "__"
}

binop_map={
    ast.Add:"__add__"
}
