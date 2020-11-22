import ast
from pystatic.option import Option
from enum import Enum
from typing import Tuple, Optional, TYPE_CHECKING
from pystatic.error_register import *

if TYPE_CHECKING:
    from pystatic.typesys import TypeIns
    from pystatic.fsys import FilePath
    from pystatic.symid import SymId


class Level(Enum):
    HINT = 1  # code unreachable
    WARN = 2  # type error
    ERROR = 3  # will cause runtime error


class ErrorCode:
    def __init__(self):
        pass

    def make(self) -> Tuple[Optional[ast.AST], str]:
        pass

    @staticmethod
    def concat_msg(review: str, detail: str):
        msg = review + "(" + detail + ")"
        return msg


class IncompatibleTypeInAssign(ErrorCode):
    def __init__(self, node: Optional[ast.AST], expect_type: 'TypeIns',
                 expr_type: 'TypeIns'):
        super().__init__()
        self.node = node
        self.expect_type = expect_type
        self.expr_type = expr_type
        self.level = Level.WARN

    def make(self) -> Tuple[Optional[ast.AST], str]:
        review = INCOMPATIBLE_TYPE_IN_ASSIGN
        detail = f"expression has type '{self.expr_type}', variable has type '{self.expect_type}'"
        return self.node, self.concat_msg(review, detail)


class SymbolUndefined(ErrorCode):
    def __init__(self, node: Optional[ast.AST], name: str):
        super().__init__()
        self.node = node
        self.name = name
        self.level = Level.ERROR

    def make(self) -> Tuple[Optional[ast.AST], str]:
        review = SYMBOL_UNDEFINED.format(self.name)
        detail = f"unresolved reference '{self.name}'"
        return self.node, self.concat_msg(review, detail)


class SymbolRedefine(ErrorCode):
    def __init__(self, node: Optional[ast.AST], name: str,
                 old_node: Optional[ast.AST]) -> None:
        super().__init__()
        self.node = node
        self.name = name
        self.old_node = old_node
        self.level = Level.WARN

    def make(self) -> Tuple[Optional[ast.AST], str]:
        review = SYMBOL_REDEFINE.format(self.name)
        if self.old_node:
            detail = f'{self.name} previously defined at line {self.old_node.lineno}'
            return self.node, self.concat_msg(review, detail)
        else:
            return self.node, review


class VarTypeCollide(ErrorCode):
    """Name has been defined as a class but used on the left of an assignment
    statement.
    """
    def __init__(self, clsnode: Optional[ast.ClassDef], name: str,
                 varnode: Optional[ast.AST]) -> None:
        super().__init__()
        self.clsnode = clsnode
        self.node = varnode
        self.name = name
        self.level = Level.WARN

    def make(self) -> Tuple[Optional[ast.AST], str]:
        review = VAR_TYPE_COLLIDE.format(self.name)
        if self.clsnode:
            detail = f'{self.name} defined as a class at line {self.clsnode.lineno}'
            return self.node, self.concat_msg(review, detail)
        else:
            return self.node, review


class IncompatibleReturnType(ErrorCode):
    def __init__(self, node: Optional[ast.AST], expect_type: 'TypeIns',
                 ret_type: 'TypeIns'):
        super().__init__()
        self.node = node
        self.expect_type = expect_type
        self.ret_type = ret_type
        self.level = Level.WARN

    def make(self) -> Tuple[Optional[ast.AST], str]:
        review = INCOMPATIBLE_RETURN_TYPE
        detail = f"expected '{self.expect_type}', got '{self.ret_type}'"
        return self.node, self.concat_msg(review, detail)


class IncompatibleArgument(ErrorCode):
    def __init__(self, node: ast.AST, func_name: str, annotation: 'TypeIns',
                 real_type: 'TypeIns'):
        super().__init__()
        self.node = node
        self.func_name = func_name
        self.annotation = annotation
        self.real_type = real_type
        self.level = Level.WARN

    def make(self) -> Tuple[Optional[ast.AST], str]:
        review = INCOMPATIBLE_ARGUMENT.format(self.func_name)
        detail = f"argument has type '{self.real_type}', expected '{self.annotation}'"
        return self.node, self.concat_msg(review, detail)


class TooFewArgument(ErrorCode):
    def __init__(self, node: Optional[ast.AST], func_name: str):
        super().__init__()
        self.node = node
        self.func_name = func_name
        self.level = Level.ERROR

    def make(self) -> Tuple[Optional[ast.AST], str]:
        return self.node, TOO_FEW_ARGUMENT_FOR_FUNC.format(self.func_name)


class TooMoreArgument(ErrorCode):
    def __init__(self, node: Optional[ast.AST], func_name: str):
        super().__init__()
        self.node = node
        self.func_name = func_name
        self.level = Level.ERROR

    def make(self) -> Tuple[Optional[ast.AST], str]:
        return self.node, TOO_MORE_ARGUMENT_FOR_FUNC.format(self.func_name)


class TooMoreValuesToUnpack(ErrorCode):
    def __init__(self, node: Optional[ast.AST], expected_num: int,
                 got_num: int):
        super().__init__()
        self.node = node
        self.expected_num = expected_num
        self.got_num = got_num
        self.level = Level.ERROR

    def make(self) -> Tuple[Optional[ast.AST], str]:
        review = TOO_MORE_VALUES_TO_UNPACK
        detail = f"expected {self.expected_num}, got {self.got_num}"
        return self.node, self.concat_msg(review, detail)


class NeedMoreValuesToUnpack(ErrorCode):
    def __init__(self, node: Optional[ast.AST], expected_num: int,
                 got_num: int):
        super().__init__()
        self.node = node
        self.expected_num = expected_num
        self.got_num = got_num
        self.level = Level.ERROR

    def make(self) -> Tuple[Optional[ast.AST], str]:
        review = NEED_MORE_VALUES_TO_UNPACK
        detail = f"expected {self.expected_num}, got {self.got_num}"
        return self.node, self.concat_msg(review, detail)


class ReturnValueExpected(ErrorCode):
    def __init__(self, node: Optional[ast.AST]):
        super().__init__()
        self.node = node
        self.level = Level.WARN

    def make(self) -> Tuple[Optional[ast.AST], str]:
        return self.node, RETURN_VALUE_EXPECTED


class NoAttribute(ErrorCode):
    def __init__(self, node: Optional[ast.AST], target_type: "TypeIns",
                 attr_name: str):
        super().__init__()
        self.node = node
        self.target_type = target_type
        self.attr_name = attr_name
        self.level = Level.WARN

    def make(self) -> Tuple[Optional[ast.AST], str]:
        msg = NO_ATTRIBUTE.format(self.target_type, self.attr_name)
        return self.node, msg


class UnsupportedBinOperand(ErrorCode):
    def __init__(self, node: Optional[ast.AST], operand: str,
                 left_type: 'TypeIns', right_type: 'TypeIns'):
        super().__init__()
        self.node = node
        self.operand = operand
        self.left_type = left_type
        self.right_type = right_type
        self.level = Level.ERROR

    def make(self) -> Tuple[Optional[ast.AST], str]:
        review = UNSUPPORTED_OPERAND.format(self.operand)
        detail = f"'{self.left_type}' and {self.right_type}"
        return self.node, self.concat_msg(review, detail)


class CodeUnreachable(ErrorCode):
    def __init__(self, node: Optional[ast.AST]):
        super().__init__()
        self.node = node
        self.level = Level.HINT

    def make(self) -> Tuple[Optional[ast.AST], str]:
        return self.node, CODE_UNREACHABLE


# Errors that have nothing to do with type inconsistency
class FileNotFound(ErrorCode):
    def __init__(self, path: 'FilePath') -> None:
        super().__init__()
        self.path = path
        self.level = Level.ERROR

    def make(self) -> Tuple[Optional[ast.AST], str]:
        return None, FILE_NOT_FOUND.format(self.path)


class ModuleNotFound(ErrorCode):
    def __init__(self, symid: 'SymId') -> None:
        super().__init__()
        self.symid = symid
        self.level = Level.ERROR

    def make(self) -> Tuple[Optional[ast.AST], str]:
        return None, MODULE_NOT_FOUND.format(self.symid)
