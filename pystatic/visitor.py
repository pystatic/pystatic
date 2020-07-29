import ast


class ParseException(Exception):
    def __init__(self, node, msg: str):
        super().__init__(msg)
        self.msg = msg
        self.node = node


class BaseVisitor(object):
    def visit(self, node: ast.AST, *args, **kwargs):
        method = 'visit_' + node.__class__.__name__
        next_visitor = getattr(self, method, self.generic_visit)
        return next_visitor(node, *args, **kwargs)

    def generic_visit(self, node: ast.AST, *args, **kwargs):
        rt = None
        for field, value in ast.iter_fields(node):
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.AST):
                        rt = self.visit(item)
            elif isinstance(value, ast.AST):
                rt = self.visit(value, *args, **kwargs)
        return rt

    def accept(self, node: ast.AST):
        return self.visit(node)
