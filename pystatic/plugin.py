import ast
from pystatic.visitor import BaseVisitor
from typing import Optional
from pystatic.typesys import TypeIns


def find_node_type(root: ast.AST, lineno: int, col_offset: int) -> Optional[TypeIns]:
    return TypeFindingVisitor(lineno, col_offset).accept(root)


def print_node(node: ast.AST):
    if hasattr(node, 'lineno'):
        print(f"lineno: {node.lineno}, end_lineno: {node.end_lineno}\n"
              f"col_offset: {node.col_offset}, end_col_offset: {node.end_col_offset}")


class TypeFindingVisitor(BaseVisitor):
    def __init__(self, lineno: int, col_offset: int):
        self.lineno = lineno
        self.col_offset = col_offset
        self.max_col_offset = 0
        self.node_type = None

    def visit(self, node, *args, **kwargs):
        if hasattr(node, 'lineno'):
            if self.lineno < node.lineno:
                return
            if self.lineno == node.lineno and self.col_offset >= node.col_offset:
                if node.col_offset >= self.max_col_offset:
                    self.max_col_offset = node.col_offset
                    if hasattr(node, 'type'):
                        self.node_type = getattr(node, 'type')
        visit_func = self.get_visit_func(node)
        return visit_func(node, *args, **kwargs)

    def accept(self, node):
        self.visit(node)
        return self.node_type
