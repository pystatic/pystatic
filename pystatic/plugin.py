import ast
from typing import Optional, List, Dict
from pystatic.typesys import TypeIns
from pystatic.errorcode import ErrorCode


class NodeType:
    def __init__(self, lineno: int, end_lineno: Optional[int], col_offset: int,
                 end_col_offset: Optional[int], node_type: 'TypeIns'):
        self.lineno = lineno
        self.end_lineno: int = end_lineno if end_lineno else lineno
        self.col_offset = col_offset
        self.end_col_offset: int = end_col_offset if end_col_offset else col_offset
        self.node_type = node_type

    @classmethod
    def from_node(cls, node: ast.AST, node_type: 'TypeIns'):
        return cls(node.lineno, node.end_lineno, node.col_offset,
                   node.end_col_offset, node_type)


class Plugin:
    def __init__(self):
        self.error_codes: List[ErrorCode] = []
        self.node_types: List[NodeType] = []

    def add_err(self, err: ErrorCode):
        self.error_codes.append(err)

    def add_type(self, node: ast.AST, node_type: TypeIns):
        self.node_types.append(NodeType.from_node(node, node_type))
