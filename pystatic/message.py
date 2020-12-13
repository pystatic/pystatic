import ast
from typing import Optional, List, TYPE_CHECKING
from pystatic.errorcode import ErrorCode, CodeUnreachable, Level
from pystatic.result import Result

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


class MessageBox(object):
    def __init__(self, module_symid: str):
        self.module_symid = module_symid
        self.error: List[ErrorCode] = []

    def add_err(self, err: ErrorCode):
        self.error.append(err)

    def to_message(self):
        msg_list = [Message.from_node(*err.make()) for err in self.error]
        return sorted(msg_list)

    def clear(self):
        self.error = []


class ErrorMaker:
    def __init__(self, mbox: MessageBox):
        self.mbox = mbox

    def dump_result(self, option: Result):
        option.dump_to_box(self.mbox)
        return option.value

    def add_err(self, err: ErrorCode):
        self.mbox.add_err(err)

    def exsit_error(self, result: Result) -> bool:
        return result.haserr()

    def generate_code_unreachable_error(self, code_frag: List[ast.stmt]):
        if len(code_frag) == 0:
            return
        begin = code_frag[0]
        end = code_frag[-1]
        begin.end_lineno = end.end_lineno
        begin.end_col_offset = end.end_col_offset
        self.add_err(CodeUnreachable(begin))

    def level_error_in_result(self, result: Result):
        if result.errors:
            for err in result.errors:
                if err.level == Level.ERROR:
                    return True
        return False
