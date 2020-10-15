import ast
from typing import Tuple, Optional
from pystatic.typesys import TypeIns

INCOMPATIBLE_TYPE_IN_ASSIGN = "Incompatible type in assignment"
SYMBOL_UNDEFINED = 'Cannot determine type of "{}"'
NO_ATTRIBUTE = 'Type "{}" has no attribute "{}"'
UNSUPPORTED_OPERAND = 'Unsupported operand types for "{}"'
# tuple
NEED_MORE_VALUES_TO_UNPACK = "Need more values to unpack"
TOO_MORE_VALUES_TO_UNPACK = "Too more values to unpack"
# ret
RETURN_VALUE_EXPECTED = "Return value expected"
INCOMPATIBLE_RETURN_TYPE = "Incompatible return value type"
# call
INCOMPATIBLE_ARGUMENT = "Incompatible argument type for '{}'"


class ErrorCode:
    def __init__(self):
        pass

    def make(self) -> Tuple[ast.AST, str]:
        pass

    @staticmethod
    def concat_msg(review: str, detail: str):
        msg = review + "(" + detail + ")"
        return msg


class IncompatibleTypeInAssign(ErrorCode):
    def __init__(self,
                 node: Optional[ast.AST],
                 expect_type: TypeIns,
                 expr_type: TypeIns):
        super().__init__()
        self.node = node
        self.expect_type = expect_type
        self.expr_type = expr_type

    def make(self) -> Tuple[Optional[ast.AST], str]:
        review = INCOMPATIBLE_TYPE_IN_ASSIGN
        detail = f"expression has type '{self.expr_type}', variable has type '{self.expect_type}'"
        return self.node, self.concat_msg(review, detail)


class SymbolUndefined(ErrorCode):
    def __init__(self,
                 node: Optional[ast.AST],
                 name: str):
        super().__init__()
        self.node = node
        self.name = name

    def make(self) -> Tuple[Optional[ast.AST], str]:
        review = SYMBOL_UNDEFINED.format(self.name)
        return self.node, review


class IncompatibleReturnType(ErrorCode):
    def __init__(self,
                 node: Optional[ast.AST],
                 expect_type: TypeIns,
                 ret_type: TypeIns):
        super().__init__()
        self.node = node
        self.expect_type = expect_type
        self.ret_type = ret_type

    def make(self) -> Tuple[Optional[ast.AST], str]:
        review = INCOMPATIBLE_RETURN_TYPE
        detail = f"expected '{self.expect_type}', got '{self.ret_type}'"
        return self.node, self.concat_msg(review, detail)


class IncompatibleArgument(ErrorCode):
    def __init__(self,
                 node: ast.AST,
                 func_name: str,
                 annotation: TypeIns,
                 real_type: TypeIns):
        super().__init__()
        self.node = node
        self.func_name = func_name
        self.annotation = annotation
        self.real_type = real_type

    def make(self) -> Tuple[Optional[ast.AST], str]:
        review = INCOMPATIBLE_ARGUMENT.format(self.func_name)
        detail = f"argument has type '{self.real_type}', expected '{self.annotation}'"
        return self.node, self.concat_msg(review, detail)


class TooMoreValuesToUnpack(ErrorCode):
    def __init__(self, node: Optional[ast.AST]):
        super().__init__()
        self.node = node

    def make(self) -> Tuple[Optional[ast.AST], str]:
        return self.node, TOO_MORE_VALUES_TO_UNPACK


class NeedMoreValuesToUnpack(ErrorCode):
    def __init__(self, node: Optional[ast.AST]):
        super().__init__()
        self.node = node

    def make(self) -> Tuple[Optional[ast.AST], str]:
        return self.node, NEED_MORE_VALUES_TO_UNPACK


class ReturnValueExpected(ErrorCode):
    def __init__(self, node: Optional[ast.AST]):
        super().__init__()
        self.node = node

    def make(self) -> Tuple[Optional[ast.AST], str]:
        return self.node, RETURN_VALUE_EXPECTED


class NoAttribute(ErrorCode):
    def __init__(self,
                 node: Optional[ast.AST],
                 target_type: TypeIns,
                 attr_name: str):
        super().__init__()
        self.node = node
        self.target_type = target_type
        self.attr_name = attr_name

    def make(self) -> Tuple[Optional[ast.AST], str]:
        msg = NO_ATTRIBUTE.format(self.target_type, self.attr_name)
        return self.node, msg


class UnsupportedBinOperand(ErrorCode):
    def __init__(self,
                 node: Optional[ast.AST],
                 operand: str,
                 left_type: TypeIns,
                 right_type: TypeIns):
        super().__init__()
        self.node = node
        self.operand = operand
        self.left_type = left_type
        self.right_type = right_type

    def make(self) -> Tuple[Optional[ast.AST], str]:
        review = UNSUPPORTED_OPERAND.format(self.operand)
        detail = f"'{self.left_type}' and {self.right_type}"
        return self.node, self.concat_msg(review, detail)
