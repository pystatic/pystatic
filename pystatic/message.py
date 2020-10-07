import ast
from typing import Optional, List

INCOMPATIBLE_TYPE_IN_ASSIGN = "Incompatible type in assignment"
SYMBOL_UNDEFINED = 'Cannot determine type of "{}"'
# tuple
NEED_MORE_VALUES_TO_UNPACK = "Need more values to unpack"
TOO_MORE_VALUES_TO_UNPACK = "Too more values to unpack"
# ret
RETURN_VALUE_EXPECTED = "Return value expected"
INCOMPATIBLE_RETURN_TYPE = "Incompatible return value type"


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
        self.filename = module_uri
        self.error: List[Message] = []

    def incompatible_type_in_assign(self, node, expect_type, expr_type):
        review = INCOMPATIBLE_TYPE_IN_ASSIGN
        detail = f"expression has type '{expr_type}', variable has type '{expect_type}'"
        self.make(node, review, detail)

    def symbol_undefined(self, node, name):
        review = SYMBOL_UNDEFINED.format(name)
        detail = f"unresolved reference {name}"
        self.make(node, review, detail)

    def incompatible_return_type(self, node, expect_type, ret_type):
        review = INCOMPATIBLE_RETURN_TYPE
        detail = f"expected '{expect_type}', got '{ret_type}'"
        self.make(node, review, detail)

    def too_more_values_to_unpack(self, node):
        self.add_err(node, TOO_MORE_VALUES_TO_UNPACK)

    def need_more_values_to_unpack(self, node):
        self.add_err(node, NEED_MORE_VALUES_TO_UNPACK)

    def return_value_expected(self, node):
        self.add_err(node, RETURN_VALUE_EXPECTED)

    def make(self, node, review, detail):
        msg = review + "(" + detail + ")"
        self.add_err(node, msg)

    def add_err(self, node: ast.AST, msg: str):
        self.error.append(Message.from_node(node, msg))

    def report(self):
        for err in self.error:
            print(err)
