import ast
from typing import Optional, List, TYPE_CHECKING
from pystatic.errorcode import ErrorCode, CodeUnreachable
from pystatic.option import Option

if TYPE_CHECKING:
    from pystatic.typesys import TypeIns


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


class TypeNode:
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


class MessageBox(object):
    def __init__(self, module_symid: str):
        self.module_symid = module_symid
        self.error: List[Message] = []
        self.types: List[TypeNode] = []

    def add_err(self, node: ast.AST, msg: str):
        self.error.append(Message.from_node(node, msg))

    def add_type(self, node: ast.AST, tp: 'TypeIns'):
        self.types.append(TypeNode.from_node(node, tp))

    def make(self, error: ErrorCode):
        node, msg = error.make()
        if node is None:
            return
        self.add_err(node, msg)

    def clear(self):
        self.error = []

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

    def add_type(self, node: ast.AST, tp: 'TypeIns'):
        self.mbox.add_type(node, tp)

    def exsit_error(self, option: Option) -> bool:
        return len(option.errors) != 0

    def generate_code_unreachable_error(self, code_frag: List[ast.stmt]):
        if len(code_frag) == 0:
            return

        begin = code_frag[0]
        end = code_frag[-1]
        begin.end_lineno = end.end_lineno
        begin.end_col_offset = end.end_col_offset
        self.add_err(CodeUnreachable(begin))
