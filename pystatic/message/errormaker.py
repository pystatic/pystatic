import ast
from typing import List

from pystatic.message.errorcode import ErrorCode, CodeUnreachable, Level
from pystatic.message.messagebox import MessageBox
from pystatic.result import Result


class ErrorMaker:
    def __init__(self, mbox: MessageBox):
        self.mbox = mbox

    def dump_result(self, option: Result):
        option.dump_to_box(self.mbox)
        return option.value

    def add_err(self, err: ErrorCode):
        self.mbox.add_err(err)

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
