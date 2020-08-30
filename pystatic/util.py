import ast
import enum
from typing import Optional, Final, List

# Uri part
Uri = str


def count_uri_head_dots(uri: Uri) -> int:
    """find out how many dots at the begining of a uri"""
    i = 0
    while len(uri) > i and uri[i] == '.':
        i += 1
    return i


def uri2list(uri: Uri) -> List[str]:
    return [item for item in uri.split('.') if item != '']


def list2uri(urilist: List[str]) -> Uri:
    return '.'.join(urilist)


def uri_parent(uri: Uri) -> Uri:
    """Return the parent uri(a.b.c -> a.b, a -> ''), uri should be absolute"""
    return '.'.join(uri2list(uri)[:-1])


def uri_last(uri: Uri) -> str:
    """Return the last(a.b.c -> c, a -> a)"""
    if not uri:
        return ''
    return uri2list(uri)[-1]


def absolute_urilist(uri: Uri, cur_uri: Uri) -> List[str]:
    i = count_uri_head_dots(uri)
    if i == 0:  # the uri itself is an absolute uri
        return uri2list(uri)
    else:
        rel_uri = uri2list(uri[i:])
        if i == 1:
            return uri2list(cur_uri) + rel_uri
        else:
            return uri2list(cur_uri)[:-(i // 2)] + rel_uri


# Enum constant part
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


# Unparse part
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


# exception part
class ParseException(Exception):
    def __init__(self, node: ast.AST, msg: str):
        super().__init__(msg)
        self.msg = msg
        self.node = node


class UnParseException(Exception):
    """Exceptions used in unparse"""
    def __init__(self,
                 node: Optional[ast.AST] = None,
                 msg: Optional[str] = None):
        self.node = node
        self.msg = msg
