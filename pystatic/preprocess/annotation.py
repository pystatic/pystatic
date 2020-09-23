import ast
from pystatic.symtable import SymTable
from typing import List, Optional, Union
from pystatic.visitor import BaseVisitor
from pystatic.typesys import (TypeIns, ellipsis_type, TypeType)


def parse_annotation(node: ast.AST, symtable: SymTable) -> Optional[TypeType]:
    return AnnotationVisitor(symtable).accept(node)


def parse_comment_annotation(comment: str,
                             symtable: SymTable) -> Optional[TypeType]:
    try:
        treenode = ast.parse(comment, mode='eval')
        if hasattr(treenode, 'body'):
            return AnnotationVisitor(symtable).accept(
                treenode.body)  # type: ignore
        else:
            return None
    except SyntaxError:
        return None


class NameNotFound(Exception):
    pass


class InvalidAnnSyntax(Exception):
    pass


class AnnotationVisitor(BaseVisitor):
    def __init__(self, symtable: SymTable) -> None:
        self.symtable = symtable

    def visit(self, node, *args, **kwargs):
        if self.whether_visit(node):
            func = self.get_visit_func(node)
            if func == self.generic_visit:
                raise InvalidAnnSyntax
            else:
                return func(node, *args, **kwargs)

    def accept(self, node) -> Optional[TypeType]:
        try:
            res = self.visit(node)
            assert isinstance(res, TypeType)
            return res
        except NameNotFound:
            return None

    def visit_Attribute(self, node: ast.Attribute) -> TypeType:
        left_type = self.visit(node.value)
        assert isinstance(left_type, TypeType)
        res_type = left_type.getattribute(node.attr)
        assert isinstance(res_type, TypeType)
        return res_type

    def visit_Ellipsis(self, node: ast.Ellipsis) -> TypeType:
        return ellipsis_type

    def visit_Name(self, node: ast.Name) -> TypeType:
        res = self.symtable.lookup_local(node.id)
        if res:
            if isinstance(res, TypeType):  # sometimes may fail
                return res
            else:
                raise NameNotFound
        else:
            raise NameNotFound

    def visit_Constant(self, node: ast.Constant) -> TypeType:
        if node.value is Ellipsis:
            return ellipsis_type
        else:
            raise NameNotFound

    def visit_Subscript(self, node: ast.Subscript) -> TypeType:
        value = self.visit(node.value)
        assert isinstance(value, TypeType)
        if isinstance(node.slice, (ast.Tuple, ast.Index)):
            if isinstance(node.slice, ast.Tuple):
                slc = self.visit(node.slice)
            else:
                # ast.Index
                slc = self.visit(node.slice.value)
            if isinstance(slc, list):
                return value.getitem(slc)[0]  # TODO: add check here
            assert isinstance(slc, TypeType)
            return value.getitem([slc])[0]  # TODO: add check here
        else:
            assert 0, "Not implemented yet"
            raise InvalidAnnSyntax

    def visit_Tuple(self, node: ast.Tuple) -> List[TypeType]:
        items = []
        for subnode in node.elts:
            res = self.visit(subnode)
            assert isinstance(res, TypeIns) or isinstance(res, list)
            items.append(res)
        return items

    def visit_List(self, node: ast.List) -> List[TypeType]:
        # ast.List and ast.Tuple has similar structure
        return self.visit_Tuple(node)  # type: ignore
