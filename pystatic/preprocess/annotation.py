import ast
from pystatic.symtable import SymTable
from typing import List, Optional, Union
from pystatic.visitor import BaseVisitor
from pystatic.env import Environment
from pystatic.message import MessageBox
from pystatic.typesys import (DeferredBindList, DeferredElement, Deferred,
                              EntryType, TypeIns, ellipsis_type, TypeType)


def parse_annotation(node: ast.AST, symtable: SymTable,
                     mbox: MessageBox) -> Optional[EntryType]:
    return AnnotationVisitor(symtable, mbox).accept(node)


def parse_comment_annotation(comment: str, symtable: SymTable,
                             mbox: MessageBox) -> Optional[EntryType]:
    try:
        treenode = ast.parse(comment, mode='eval')
        if hasattr(treenode, 'body'):
            return AnnotationVisitor(symtable, mbox).accept(
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
    def __init__(self, symtable: SymTable, mbox: MessageBox) -> None:
        self.symtable = symtable
        self.mbox = mbox

    def visit(self, node, *args, **kwargs):
        if self.whether_visit(node):
            func = self.get_visit_func(node)
            if func == self.generic_visit:
                raise InvalidAnnSyntax
            else:
                return func(node, *args, **kwargs)

    def invalid_syntax(self, node: ast.AST) -> None:
        self.mbox.add_err(node, 'invalid annotation syntax')
        return None

    def accept(self, node) -> Optional[EntryType]:
        try:
            res = self.visit(node)
            assert isinstance(res, TypeType)
            return res
        except NameNotFound:
            try:
                return DeferVisitor(self.mbox).accept(node)
            except InvalidAnnSyntax:
                return self.invalid_syntax(node)
        except InvalidAnnSyntax as e:
            return self.invalid_syntax(node)

    def visit_Attribute(self, node: ast.Attribute) -> TypeType:
        # the assertion in this method may be too strong.
        # TODO: relax this and throw proper exception after detecting a failure
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


class DeferVisitor(BaseVisitor):
    def __init__(self, mbox: MessageBox) -> None:
        self.mbox = mbox

    def str_to_dfele(self, name: str) -> DeferredElement:
        return DeferredElement(name, DeferredBindList())

    def ele_to_defer(self, element: DeferredElement) -> Deferred:
        defer = Deferred()
        defer.add_element(element)
        return defer

    def visit(self, node, *args, **kwargs):
        if self.whether_visit(node):
            func = self.get_visit_func(node)
            if func == self.generic_visit:
                raise InvalidAnnSyntax
            else:
                res = func(node, *args, **kwargs)
                return res

    def accept(self, node) -> Optional[Deferred]:
        try:
            res = self.visit(node)
            if isinstance(res, DeferredElement):
                return self.ele_to_defer(res)
            elif isinstance(res, Deferred):
                return res
            else:
                self.mbox.add_err(node, 'invalid annotation syntax')
                return None
        except InvalidAnnSyntax as e:
            self.mbox.add_err(node, 'invalid annotation syntax')
            return None

    def visit_Attribute(self, node: ast.Attribute) -> Deferred:
        left_res = self.visit(node.value)
        if isinstance(node.attr, str):
            attr_ele = self.str_to_dfele(node.attr)
        else:
            attr_ele = self.visit(node.attr)

        assert isinstance(left_res, (Deferred, DeferredElement))
        assert isinstance(attr_ele, DeferredElement)

        if isinstance(left_res, DeferredElement):
            defer = self.ele_to_defer(left_res)
            defer.add_element(attr_ele)
            return defer
        else:
            left_res.add_element(attr_ele)
            return left_res

    def visit_Ellipsis(self, node: ast.Ellipsis) -> DeferredElement:
        return self.str_to_dfele('...')

    def visit_Name(self, node: ast.Name) -> DeferredElement:
        return self.str_to_dfele(node.id)

    def visit_Constant(self, node: ast.Constant) -> DeferredElement:
        if node.value is Ellipsis:
            return self.str_to_dfele('...')
        elif isinstance(
                node.value,
                str,
        ):
            return self.str_to_dfele(node.value)
        else:
            raise InvalidAnnSyntax

    def visit_Subscript(
            self, node: ast.Subscript) -> Union[Deferred, DeferredElement]:
        value = self.visit(node.value)
        assert isinstance(value, (Deferred, DeferredElement))
        if isinstance(value, Deferred):
            to_bind = value.get(-1)
        else:
            # DeferredElement
            to_bind = value
        assert isinstance(to_bind, DeferredElement)  # NOTE: this may be fail
        if to_bind.get_bind_cnt() != 0:
            raise InvalidAnnSyntax
        if isinstance(node.slice, (ast.Tuple, ast.Index)):
            if isinstance(node.slice, ast.Tuple):
                slc = self.visit(node.slice)
            else:
                # ast.Index
                slc = self.visit(node.slice.value)
            bindlist = DeferredBindList()
            if isinstance(slc, list):
                for defer in slc:
                    bindlist.add_binded(defer)
            else:
                assert isinstance(slc, (Deferred, DeferredElement))
                bindlist.add_binded(slc)
            to_bind.bindlist = bindlist
            return value
        else:
            assert 0, "Not implemented yet"
            raise InvalidAnnSyntax

    def visit_Tuple(self, node: ast.Tuple) -> List[Deferred]:
        items: List[Deferred] = []
        for subnode in node.elts:
            res = self.visit(subnode)
            if isinstance(res, str):
                defer = self.ele_to_defer(self.str_to_dfele(res))
                items.append(defer)
            elif isinstance(res, DeferredElement):
                items.append(self.ele_to_defer(res))
            elif isinstance(res, Deferred):
                items.append(res)
            elif isinstance(res, list):
                items.append(res)
            else:
                assert 0, "should not reach here"
                raise InvalidAnnSyntax
        return items

    def visit_List(self, node: ast.List) -> List[Deferred]:
        # ast.List and ast.Tuple has similar structure
        return self.visit_Tuple(node)  # type: ignore
