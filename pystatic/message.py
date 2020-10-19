import ast
from typing import Optional, List
from pystatic.errorcode import ErrorCode
from pystatic.option import Option


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
    def __init__(self, module_uri: str):
        self.module_uri = module_uri
        self.error: List[Message] = []

    def add_err(self, node: ast.AST, msg: str):
        self.error.append(Message.from_node(node, msg))

    def make(self, error: ErrorCode):
        node, msg = error.make()
        if node is None:
            return
        self.add_err(node, msg)

    def report(self):
        for err in self.error:
            print(err)


class ErrorMaker:
    def __init__(self, mbox: MessageBox):
        self.mbox = mbox

    def dump_option(self, option: Option):
        self.handle_err(option.errors)
        return option.value

    def handle_err(self, err_list: List[ErrorCode]):
        if err_list is None:
            return
        for err in err_list:
            self.mbox.make(err)

    def add_err(self, err: ErrorCode):
        self.mbox.make(err)

    def exsit_error(self, option: Option) -> bool:
        return len(option.errors) != 0