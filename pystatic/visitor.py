import ast
from typing import Optional
from pystatic.reach import Reach
from pystatic.util import ParseException


class BaseVisitor(object):
    def whether_visit(self, node):
        if getattr(node, 'reach',
                   Reach.UNKNOWN) not in (Reach.NEVER, Reach.CLS_REDEF):
            return True
        return False

    def get_visit_func(self, node):
        method = 'visit_' + node.__class__.__name__
        next_visitor = getattr(self, method, self.generic_visit)
        return next_visitor

    def visit(self, node, *args, **kwargs):
        if self.whether_visit(node):
            visit_func = self.get_visit_func(node)
            return visit_func(node, *args, **kwargs)

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


class VisitorMethodNotFound(Exception):
    pass


class NoGenVisitor(BaseVisitor):
    def __init__(self):
        super().__init__()

    def visit(self, node, *args, **kwargs):
        if self.whether_visit(node):
            visit_func = self.get_visit_func(node)
            if visit_func == self.generic_visit:
                raise VisitorMethodNotFound
            else:
                return visit_func(node, *args, **kwargs)


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
    """Tries to change the ast to the str format

    May throw ParseException
    """
    return LiterUnParser().accept(node)
