import ast
import enum
from typing import Optional, Final


class Reach(enum.Enum):
    TYPE_TRUE = 1  # type: Final
    TYPE_FALSE = 2  # type: Final
    RUNTIME_TRUE = 3  # type: Final
    RUNTIME_FALSE = 4  # type: Final
    ALWAYS_TRUE = 5  # type: Final
    ALWAYS_FALSE = 6  # type: Final
    CLS_REDEF = 7  # type: Final
    NEVER = 8
    UNKNOWN = 9  # type: Final


class BaseVisitor(object):
    def __init__(self) -> None:
        # node with reachability in reach_block will not be visited
        self.reach_block: tuple = (Reach.NEVER, Reach.CLS_REDEF)

    def visit(self, node, *args, **kwargs):
        if getattr(node, 'reach', Reach.UNKNOWN) not in self.reach_block:
            method = 'visit_' + node.__class__.__name__
            next_visitor = getattr(self, method, self.generic_visit)
            return next_visitor(node, *args, **kwargs)

    def generic_visit(self, node, *args, **kwargs):
        rt = None
        for field, value in ast.iter_fields(node):
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.AST):
                        rt = self.visit(item)
            elif isinstance(value, ast.AST):
                rt = self.visit(value, *args, **kwargs)
        return rt

    def accept(self, node):
        return self.visit(node)


class ParseException(Exception):
    def __init__(self, node: ast.AST, msg: str):
        super().__init__(msg)
        self.msg = msg
        self.node = node


class UnParseException(Exception):
    def __init__(self,
                 node: Optional[ast.AST] = None,
                 msg: Optional[str] = None):
        self.node = node
        self.msg = msg


class UnParser(BaseVisitor):
    def __init__(self, context: Optional[dict]) -> None:
        super().__init__()
        self.context = context

    def visit(self, node: ast.AST, *args, **kwargs):
        method = 'visit_' + node.__class__.__name__
        next_visitor = getattr(self, method, None)
        if not next_visitor:
            raise UnParseException()
        return next_visitor(node, *args, **kwargs)

    def visit_Tuple(self, node: ast.Tuple):
        items = []
        for subnode in node.elts:
            items.append(self.visit(subnode))
        return tuple(items)

    def visit_Name(self, node: ast.Name):
        if self.context and node.id in self.context:
            return self.context[node.id]
        raise UnParseException()

    def visit_Constant(self, node: ast.Constant):
        try:
            return int(node.value)
        except ValueError:
            return node.value


def unparse(node: ast.AST, context: Optional[dict] = None):
    return UnParser(context).accept(node)
