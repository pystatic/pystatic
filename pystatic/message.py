import ast
from typing import Optional, List, Dict
from pystatic.errorcode import ErrorCode, NoError


class Message(object):
    """Message

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


class MessageBox(object):
    def __init__(self):
        self.error: Dict[str, List[Message]] = {}

    def add_err(self, module_path, node: ast.AST, msg: str):
        self.error[module_path].append(Message.from_node(node, msg))

    def make(self, error: ErrorCode):
        module_path, node, msg = error.make()
        if node is None:
            return
        self.add_err(module_path, node, msg)

    def report(self):
        for key in self.error.keys():
            for err in self.error[key]:
                print(err)
