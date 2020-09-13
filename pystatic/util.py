import ast
from typing import List, Tuple


# exception part
class ParseException(Exception):
    """ParseException is used when working on the ast tree however the tree
    doesn't match the structure and the process failed.

    Node points to the position where the process failed.
    Msg is used to describe why it failed(it can be omitted by set it to '').
    """
    def __init__(self, node: ast.AST, msg: str):
        super().__init__(msg)
        self.node = node
        self.msg = msg


BindError = List[Tuple[int, str]]


class BindException(Exception):
    """BindException is used when some error happens trying to bind types to
    typevars.

    Each element of index tells the position(start from 0) of the wrong binding
    and the error information.

    If index is empty([]), then the error information is stored in msg.
    """
    def __init__(self, errors: List[Tuple[int, str]], msg: str) -> None:
        self.msg = msg
        self.errors = errors
