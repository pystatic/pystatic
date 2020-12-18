import ast
from pystatic.error.position import ast_to_position
from typing import Sequence, Tuple, Optional, TYPE_CHECKING, Union, List, Protocol
from pystatic.error.level import Level
from pystatic.error.message import Message, PositionMessage

if TYPE_CHECKING:
    from pystatic.typesys import TypeIns
    from pystatic.fsys import FilePath
    from pystatic.symid import SymId
    from pystatic.error.errorbox import ErrorBox


MANAGER_TAG = "__MANAGER_TAG__"


class Sendable(Protocol):
    def send(self, tag: str, msg: Message):
        ...


class HasTag(Protocol):
    tag: str


class ErrorCode:
    __slots__ = ["level", "node"]

    def __init__(self, level: Level, node: Optional[ast.AST]):
        self.level = level
        self.node = node

    def to_string(self) -> str:
        ...

    def send_message(self, box: HasTag, mailman: Sendable):
        if self.node:
            msg = PositionMessage(
                self.level, ast_to_position(self.node), self.to_string()
            )
        else:
            msg = Message(self.level, self.to_string())
        mailman.send(box.tag, msg)

    @staticmethod
    def concat_msg(review: str, detail: str) -> str:
        msg = review + "(" + detail + ")"
        return msg


class IncompatibleTypeInAssign(ErrorCode):
    template = "Incompatible type in assignment"

    def __init__(
        self, node: Optional[ast.AST], expect_type: "TypeIns", expr_type: "TypeIns"
    ):
        super().__init__(Level.WARN, node)
        self.expect_type = expect_type
        self.expr_type = expr_type

    def to_string(self) -> str:
        review = self.template
        detail = f"expression has type '{self.expr_type}', variable has type '{self.expect_type}'"
        return self.concat_msg(review, detail)


class SymbolUndefined(ErrorCode):
    template = "Cannot determine type of '{}'"

    def __init__(self, node: Optional[ast.AST], name: str):
        super().__init__(Level.WARN, node)
        self.name = name

    def to_string(self) -> str:
        detail = f"unresolved reference '{self.name}'"
        return self.concat_msg(self.template.format(self.name), detail)


class SymbolRedefine(ErrorCode):
    template = "'{}' has already defined"

    def __init__(
        self, node: Optional[ast.AST], name: str, old_node: Optional[ast.AST]
    ) -> None:
        super().__init__(Level.WARN, node)
        self.name = name
        self.old_node = old_node

    def to_string(self) -> str:
        review = self.template.format(self.name)
        if self.old_node:
            detail = f"{self.name} previously defined at line {self.old_node.lineno}"
            return self.concat_msg(review, detail)
        else:
            return review


class IndiceParamNotClass(ErrorCode):
    template = "Expect a class type"

    def __init__(self, node: Optional[ast.AST]) -> None:
        super().__init__(Level.WARN, node)

    def to_string(self) -> str:
        return self.template


class IndiceParamNumberMismatch(ErrorCode):
    template = "receive {} but require {} argument(s)"

    def __init__(self, receive: int, arity: int, node: Optional[ast.AST]):
        super().__init__(Level.ERROR, node)
        self.receive = receive
        self.arity = arity

    def to_string(self) -> str:
        return self.template.format(self.receive, self.arity)


class IndiceGeneralError(ErrorCode):
    def __init__(self, msg: str, node: Optional[ast.AST]):
        super().__init__(Level.ERROR, node)
        self.msg = msg

    def to_string(self) -> str:
        return self.msg


class NotSubscriptable(ErrorCode):
    template = "type '{}' is not subscriptable"

    def __init__(self, inable_type: "TypeIns", node: Optional[ast.AST]) -> None:
        super().__init__(Level.ERROR, node)
        self.inable_type = inable_type

    def to_string(self) -> str:
        return self.template.format(self.inable_type)


class NotCallable(ErrorCode):
    template = "{} is not callable"

    def __init__(self, inable_type: "TypeIns", node: Optional[ast.AST]):
        super().__init__(Level.ERROR, node)
        self.inable_type = inable_type

    def to_string(self) -> str:
        return self.template.format(self.inable_type)


class OperationNotSupported(ErrorCode):
    """Doesn't support the operation(like '<', '>', ...)"""

    template = "{} is not supported in {}"

    def __init__(self, op_str: str, typeins: "TypeIns", node: Optional[ast.AST]):
        super().__init__(Level.ERROR, node)
        self.op_str = op_str
        self.typeins = typeins

    def to_string(self) -> str:
        return self.template.format(self.op_str, self.typeins)


class VarTypeCollide(ErrorCode):
    """Name has been defined as a class or function but used on the left of an
    assignment statement.
    """

    template = "'{}' doesn't match its definition"

    def __init__(
        self,
        previlege_node: Optional[Union[ast.ClassDef, ast.FunctionDef]],
        name: str,
        varnode: Optional[ast.AST],
    ) -> None:
        super().__init__(Level.WARN, varnode)
        self.previledge_node = previlege_node
        self.name = name

    def to_string(self) -> str:
        review = self.template.format(self.name)
        if self.previledge_node:
            if isinstance(self.previledge_node, ast.ClassDef):
                detail = f"{self.name} defined as a class at line {self.previledge_node.lineno}"
            else:
                assert isinstance(self.previledge_node, ast.FunctionDef)
                detail = f"{self.name} defined as a function at line {self.previledge_node.lineno}"
            return self.concat_msg(review, detail)
        else:
            return review


class IncompatibleReturnType(ErrorCode):
    template = "Incompatible return value type"

    def __init__(
        self, node: Optional[ast.AST], expect_type: "TypeIns", ret_type: "TypeIns"
    ):
        super().__init__(Level.WARN, node)
        self.expect_type = expect_type
        self.ret_type = ret_type

    def to_string(self) -> str:
        review = self.template
        detail = f"expected '{self.expect_type}', got '{self.ret_type}'"
        return self.concat_msg(review, detail)


class IncompatibleArgument(ErrorCode):
    template = "Incompatible type for parameter {}"

    def __init__(
        self, node: ast.AST, param_name: str, param_type: "TypeIns", arg_type: "TypeIns"
    ):
        super().__init__(Level.WARN, node)
        self.param_name = param_name
        self.param_type = param_type
        self.arg_type = arg_type

    def to_string(self) -> str:
        review = self.template.format(self.param_name)
        detail = f"get '{self.arg_type}', expect '{self.param_type}'"
        return self.concat_msg(review, detail)


class TooFewArgument(ErrorCode):
    template = "Too few arguments"

    def __init__(self, node: Optional[ast.AST], missing_names: List[str]):
        super().__init__(Level.ERROR, node)
        assert missing_names
        self.missing_names = missing_names

    def to_string(self) -> str:
        detail = f"missing " + ", ".join(self.missing_names)
        return self.concat_msg(self.template, detail)


class TooMoreArgument(ErrorCode):
    template = "Too more arguments"

    def __init__(self, node: Optional[ast.AST]):
        super().__init__(Level.ERROR, node)
        self.node = node
        self.level = Level.ERROR

    def to_string(self) -> str:
        return self.template


class TooMoreValuesToUnpack(ErrorCode):
    template = "Too more values to unpack"

    def __init__(self, node: Optional[ast.AST], expected_num: int, got_num: int):
        super().__init__(Level.ERROR, node)
        self.expected_num = expected_num
        self.got_num = got_num

    def to_string(self) -> str:
        detail = f"expected {self.expected_num}, got {self.got_num}"
        return self.concat_msg(self.template, detail)


class NeedMoreValuesToUnpack(ErrorCode):
    template = "Need more values to unpack"

    def __init__(self, node: Optional[ast.AST], expected_num: int, got_num: int):
        super().__init__(Level.ERROR, node)
        self.node = node
        self.expected_num = expected_num
        self.got_num = got_num

    def to_string(self) -> str:
        detail = f"expected {self.expected_num}, got {self.got_num}"
        return self.concat_msg(self.template, detail)


class ReturnValueExpected(ErrorCode):
    template = "Return value expected"

    def __init__(self, node: Optional[ast.AST]):
        super().__init__(Level.WARN, node)
        self.node = node
        self.level = Level.WARN

    def to_string(self) -> str:
        return self.template


class NoAttribute(ErrorCode):
    template = "Type '{}' has no attribute '{}'"

    def __init__(self, node: Optional[ast.AST], target_type: "TypeIns", attr_name: str):
        super().__init__(Level.WARN, node)
        self.target_type = target_type
        self.attr_name = attr_name

    def to_string(self) -> str:
        return self.template.format(self.target_type, self.attr_name)


class UnsupportedBinOperand(ErrorCode):
    template = "Unsupported operand types for '{}'"

    def __init__(
        self,
        node: Optional[ast.AST],
        operand: str,
        left_type: "TypeIns",
        right_type: "TypeIns",
    ):
        super().__init__(Level.ERROR, node)
        self.operand = operand
        self.left_type = left_type
        self.right_type = right_type

    def to_string(self) -> str:
        review = self.template.format(self.operand)
        detail = f"'{self.left_type}' and {self.right_type}"
        return self.concat_msg(review, detail)


class CodeUnreachable(ErrorCode):
    template = "This code is unreachable"

    def __init__(self, node: Optional[ast.AST]):
        super().__init__(Level.HINT, node)

    def to_string(self) -> str:
        return self.template


class NonIterative(ErrorCode):
    template = "type '{}' is non-iterative"

    def __init__(self, node: Optional[ast.AST], fake_iter: "TypeIns"):
        super().__init__(Level.WARN, node)
        self.iter = fake_iter

    def to_string(self) -> str:
        return self.template.format(self.iter)


# Class related
class DuplicateBaseclass(ErrorCode):
    template = "duplicate baseclass is not allowed"

    def __init__(self, node: Optional[ast.AST]) -> None:
        super().__init__(Level.ERROR, node)

    def to_string(self) -> str:
        return self.template


# Errors that have nothing to do with type inconsistency
class FileNotFound(ErrorCode):
    template = "{} not found"

    def __init__(self, path: "FilePath") -> None:
        super().__init__(Level.ERROR, None)
        self.path = path

    def to_string(self) -> str:
        return self.template.format(self.path)


class ModuleNotFound(ErrorCode):
    template = "{} not found"

    def __init__(self, symid: "SymId") -> None:
        super().__init__(Level.ERROR, None)
        self.symid = symid

    def to_string(self) -> str:
        return self.template.format(self.symid)


class ReferenceLoop(ErrorCode):
    def __init__(self, nodelist: Sequence[Tuple["SymId", ast.AST]]):
        super().__init__(Level.WARN, None)
        self.nodelist = nodelist

    def to_string(self) -> str:
        return ""
