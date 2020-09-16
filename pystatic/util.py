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
