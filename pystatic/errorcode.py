import ast
from enum import Enum
from typing import Tuple, Optional, TYPE_CHECKING, Union, List
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
        ...

    @staticmethod
    def concat_msg(review: str, detail: str):
        msg = review + "(" + detail + ")"
        return msg


class IncompatibleTypeInAssign(ErrorCode):
    def __init__(
        self, node: Optional[ast.AST], expect_type: "TypeIns", expr_type: "TypeIns"
    ):
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
    def __init__(
        self, node: Optional[ast.AST], name: str, old_node: Optional[ast.AST]
    ) -> None:
        super().__init__()
        self.node = node
        self.name = name
        self.old_node = old_node
        self.level = Level.WARN

    def make(self) -> Tuple[Optional[ast.AST], str]:
        review = SYMBOL_REDEFINE.format(self.name)
        if self.old_node:
            detail = f"{self.name} previously defined at line {self.old_node.lineno}"
            return self.node, self.concat_msg(review, detail)
        else:
            return self.node, review


class IndiceParamNotClass(ErrorCode):
    def __init__(self, node: Optional[ast.AST]) -> None:
        super().__init__()
        self.node = node
        self.level = Level.ERROR

    def make(self) -> Tuple[Optional[ast.AST], str]:
        return self.node, INDICE_PARAM_NOT_CLASS


class IndiceParamNumberMismatch(ErrorCode):
    def __init__(self, receive: int, arity: int, node: Optional[ast.AST]):
        self.receive = receive
        self.arity = arity
        self.node = node
        self.level = Level.ERROR

    def make(self) -> Tuple[Optional[ast.AST], str]:
        return self.node, INDICE_ARGUMENT_NUMBER_MISMATCH.format(
            self.receive, self.arity
        )


class IndiceGeneralError(ErrorCode):
    def __init__(self, msg: str, node: Optional[ast.AST]):
        super().__init__()
        self.msg = msg
        self.node = node
        self.level = Level.ERROR

    def make(self) -> Tuple[Optional[ast.AST], str]:
        return self.node, self.msg


class NotSubscriptable(ErrorCode):
    def __init__(self, inable_type: "TypeIns", node: Optional[ast.AST]) -> None:
        super().__init__()
        self.node = node
        self.inable_type = inable_type

    def make(self) -> Tuple[Optional[ast.AST], str]:
        return self.node, NOT_SUBSCRIPTABLE.format(self.inable_type)


class NotCallable(ErrorCode):
    def __init__(self, inable_type: "TypeIns", node: Optional[ast.AST]):
        super().__init__()
        self.node = node
        self.inable_type = inable_type

    def make(self) -> Tuple[Optional[ast.AST], str]:
        return self.node, NOT_CALLABLE.format(self.inable_type)


class VarTypeCollide(ErrorCode):
    """Name has been defined as a class or function but used on the left of an
    assignment statement.
    """

    def __init__(
        self,
        previlege_node: Optional[Union[ast.ClassDef, ast.FunctionDef]],
        name: str,
        varnode: Optional[ast.AST],
    ) -> None:
        super().__init__()
        self.previledge_node = previlege_node
        self.node = varnode
        self.name = name
        self.level = Level.WARN

    def make(self) -> Tuple[Optional[ast.AST], str]:
        review = VAR_TYPE_COLLIDE.format(self.name)
        if self.previledge_node:
            if isinstance(self.previledge_node, ast.ClassDef):
                detail = f"{self.name} defined as a class at line {self.previledge_node.lineno}"
            else:
                assert isinstance(self.previledge_node, ast.FunctionDef)
                detail = f"{self.name} defined as a function at line {self.previledge_node.lineno}"
            return self.node, self.concat_msg(review, detail)
        else:
            return self.node, review


class IncompatibleReturnType(ErrorCode):
    def __init__(
        self, node: Optional[ast.AST], expect_type: "TypeIns", ret_type: "TypeIns"
    ):
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
    def __init__(
        self, node: ast.AST, param_name: str, param_type: "TypeIns", arg_type: "TypeIns"
    ):
        super().__init__()
        self.node = node
        self.param_name = param_name
        self.param_type = param_type
        self.arg_type = arg_type
        self.level = Level.WARN

    def make(self) -> Tuple[Optional[ast.AST], str]:
        review = INCOMPATIBLE_ARGUMENT.format(self.param_name)
        detail = f"get '{self.arg_type}', expect '{self.param_type}'"
        return self.node, self.concat_msg(review, detail)


class TooFewArgument(ErrorCode):
    def __init__(self, node: Optional[ast.AST], missing_names: List[str]):
        super().__init__()
        self.node = node
        assert missing_names
        self.missing_names = missing_names
        self.level = Level.ERROR

    def make(self) -> Tuple[Optional[ast.AST], str]:
        review = TOO_FEW_ARGUMENTS
        detail = f"missing " + ", ".join(self.missing_names)
        return self.node, self.concat_msg(review, detail)


class TooMoreArgument(ErrorCode):
    def __init__(self, node: Optional[ast.AST]):
        super().__init__()
        self.node = node
        self.level = Level.ERROR

    def make(self) -> Tuple[Optional[ast.AST], str]:
        return self.node, TOO_MORE_ARGUMENTS


class TooMoreValuesToUnpack(ErrorCode):
    def __init__(self, node: Optional[ast.AST], expected_num: int, got_num: int):
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
    def __init__(self, node: Optional[ast.AST], expected_num: int, got_num: int):
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
    def __init__(self, node: Optional[ast.AST], target_type: "TypeIns", attr_name: str):
        super().__init__()
        self.node = node
        self.target_type = target_type
        self.attr_name = attr_name
        self.level = Level.WARN

    def make(self) -> Tuple[Optional[ast.AST], str]:
        msg = NO_ATTRIBUTE.format(self.target_type, self.attr_name)
        return self.node, msg


class UnsupportedBinOperand(ErrorCode):
    def __init__(
        self,
        node: Optional[ast.AST],
        operand: str,
        left_type: "TypeIns",
        right_type: "TypeIns",
    ):
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


class NonIterative(ErrorCode):
    def __init__(self, node: Optional[ast.AST], fake_iter: "TypeIns"):
        super().__init__()
        self.node = node
        self.iter = fake_iter
        self.level = Level.WARN

    def make(self) -> Tuple[Optional[ast.AST], str]:
        return self.node, NON_ITERATIVE.format(self.iter)


# Class related
class DuplicateBaseclass(ErrorCode):
    def __init__(self, node: Optional[ast.AST]) -> None:
        super().__init__()
        self.node = node
        self.level = Level.ERROR

    def make(self) -> Tuple[Optional[ast.AST], str]:
        return self.node, DUPLICATE_BASECLASS


# Errors that have nothing to do with type inconsistency
class FileNotFound(ErrorCode):
    def __init__(self, path: "FilePath") -> None:
        super().__init__()
        self.path = path
        self.level = Level.ERROR

    def make(self) -> Tuple[Optional[ast.AST], str]:
        return None, FILE_NOT_FOUND.format(self.path)


class ModuleNotFound(ErrorCode):
    def __init__(self, symid: "SymId") -> None:
        super().__init__()
        self.symid = symid
        self.level = Level.ERROR

    def make(self) -> Tuple[Optional[ast.AST], str]:
        return None, MODULE_NOT_FOUND.format(self.symid)
