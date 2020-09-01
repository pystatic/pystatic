import ast
import enum
from typing import Optional, Final, List, TYPE_CHECKING

if TYPE_CHECKING:
    from pystatic.env import Environment

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


class ValueUnParser(BaseVisitor):
    """Try to convert an ast to a python value"""
    def __init__(self, context: Optional[dict]) -> None:
        super().__init__()
        self.context = context

    def visit(self, node: ast.AST, *args, **kwargs):
        method = 'visit_' + node.__class__.__name__
        next_visitor = getattr(self, method, None)
        if not next_visitor:
            raise ParseException(node, '')
        return next_visitor(node, *args, **kwargs)

    def visit_Tuple(self, node: ast.Tuple):
        items = []
        for subnode in node.elts:
            items.append(self.visit(subnode))
        return tuple(items)

    def visit_Name(self, node: ast.Name):
        if self.context and node.id in self.context:
            return self.context[node.id]
        else:
            raise ParseException(node, f'{node.id} not found')

    def visit_Constant(self, node: ast.Constant):
        try:
            return int(node.value)
        except ValueError:
            return node.value


def val_unparse(node: ast.AST, context: Optional[dict] = None):
    """Tries to unparse node to exact values.

    Look up context when meeting variable names
    """
    return ValueUnParser(context).accept(node)


class LiterUnParser(BaseVisitor):
    def __init__(self) -> None:
        super().__init__()

    def visit(self, node: ast.AST, *args, **kwargs):
        method = 'visit_' + node.__class__.__name__
        next_visitor = getattr(self, method, None)
        if not next_visitor:
            raise ParseException(node, f'{method} not implemented')
        return next_visitor(node, *args, **kwargs)

    def visit_Name(self, node: ast.Name):
        return node.id

    def visit_Ellipsis(self, node: ast.Ellipsis):
        return '...'

    def visit_Constant(self, node: ast.Constant):
        try:
            if node.value is Ellipsis:
                return '...'
            else:
                return str(node.value)
        except ValueError:
            raise ParseException(node, "can't convert to str")

    def visit_Tuple(self, node: ast.Tuple):
        items = []
        for subnode in node.elts:
            items.append(self.visit(subnode))
        return '(' + ','.join(items) + ')'

    def visit_List(self, node: ast.List):
        items = []
        for subnode in node.elts:
            items.append(self.visit(subnode))
        return '[' + ','.join(items) + ']'

    def visit_Attribute(self, node: ast.Attribute):
        value = self.visit(node.value)
        return value + '.' + node.attr

    def visit_Subscript(self, node: ast.Subscript):
        value = self.visit(node.value)
        if isinstance(node.slice, ast.Tuple):
            slc = self.visit(node.slice)
            assert (slc[0] == '(')
            assert (slc[-1] == ')')
            slc[0] = '['
            slc[-1] = ']'
        else:
            slc = '[' + self.visit(node.slice) + ']'
        return value + slc

    def visit_Slice(self, node: ast.Slice):
        lower = ''
        upper = ''
        step = ''
        if node.lower:
            lower = self.visit(node.lower)
        if node.upper:
            upper = self.visit(node.upper)
        if node.step:
            step = self.visit(node.step)
        return ':'.join([lower, upper, step])

    def visit_Index(self, node: ast.Index):
        # ast.Index is deprecated since python3.9
        if isinstance(node.value, ast.Tuple):
            res = self.visit(node.value)
            assert res[0] == '(' and res[-1] == ')'
            return res[1:-1]
        else:
            return self.visit(node.value)

    def visit_ExtSlice(self, node: ast.ExtSlice):
        items = []
        for subnode in node.dims:
            items.append(self.visit(subnode))
        return ','.join(items)


def liter_unparse(node: ast.AST):
    """Tries to change the ast to the str format"""
    return LiterUnParser().accept(node)


# exception part
class ParseException(Exception):
    """ParseException is used when working on the ast tree however the tree
    doesn't match the structure and the process failed.

    node points to the position where the process failed.
    msg is used to describe why it failed(it can be omitted by set it to '').
    """
    def __init__(self, node: ast.AST, msg: str):
        super().__init__(msg)
        self.node = node
        self.msg = msg
