import sys
import ast
from typing import Optional
from pystatic.visitor import BaseVisitor


class ParseException(Exception):
    def __init__(self, node, msg: str):
        super().__init__(msg)
        self.msg = msg
        self.node = node


class UnParseException(Exception):
    pass


class UnParser(BaseVisitor):
    def __init__(self, context: Optional[dict]) -> None:
        self.context = context

    def visit(self, node: ast.AST, *args, **kwargs):
        method = 'visit_' + node.__class__.__name__
        next_visitor = getattr(self, method, None)
        if not next_visitor:
            raise UnParseException()
        return next_visitor(node, *args, **kwargs)

    def visit_Tuple(self, node: ast.Tuple):
        items = []
        for subnode in node.elts:
            items.append(self.visit(subnode))
        return tuple(items)

    def visit_Name(self, node: ast.Name):
        if self.context and node.id in self.context:
            return self.context[node.id]
        raise UnParseException()

    def visit_Constant(self, node: ast.Constant):
        try:
            return int(node.value)
        except ValueError:
            return node.value


def unparse(node: ast.AST, context: Optional[dict] = None):
    return UnParser(context).accept(node)
