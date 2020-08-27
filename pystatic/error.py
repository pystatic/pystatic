import ast
from typing import Optional, List


class ErrInfo(object):
    """Error information

    from_node: generate an error message for the position implied by the node
    """
    def __init__(self, lineno: int, end_lineno: Optional[int], col_offset: int,
                 end_col_offset: Optional[int], msg: str):
        self.lineno = lineno
        self.end_lineno: int = end_lineno if end_lineno else lineno
        self.col_offset = col_offset
        self.end_col_offset: int = end_col_offset if end_col_offset else col_offset
        self.msg = msg

    @classmethod
    def from_node(cls, node: ast.AST, msg: str):
        return cls(node.lineno, node.end_lineno, node.col_offset,
                   node.end_col_offset, msg)

    def __lt__(self, other):
        """ used for sort. """
        return ((self.lineno, self.col_offset, self.end_lineno,
                 self.end_col_offset) <
                (other.lineno, other.col_offset, other.end_lineno,
                 other.end_col_offset))

    def __str__(self):
        return f'line {self.lineno} col {self.col_offset}: ' + self.msg


class ErrHandler(object):
    def __init__(self, module_uri: str):
        self.filename = module_uri
        self.err: List[ErrInfo] = []

    def add_err(self, node: ast.AST, msg: str):
        new_err = ErrInfo.from_node(node, msg)
        self.err.append(new_err)

    def __iter__(self):
        self.err.sort()
        return iter(self.err)

    def __str__(self):
        self.err.sort()
        return '\n'.join([self.filename + ': ' + str(e) for e in self.err])
