import ast
from typing import Optional
from pystatic.exprparse import ExprParser, SupportGetAttribute
from pystatic.typesys import TypeIns, TypeType
from pystatic.visitor import NoGenVisitor, VisitorMethodNotFound
from pystatic.option import Option


def omit_inst_typetype(node: ast.AST,
                       consultant: SupportGetAttribute) -> Optional[TypeType]:
    """Get typetype a node represents while omitting instantiate args"""
    try:
        res = TypeTypeGetter(consultant).accept(node)
        assert isinstance(res, TypeType)
        return res
    except (ParseError, VisitorMethodNotFound):
        return None


class ParseError(Exception):
    pass


class TypeTypeGetter(NoGenVisitor):
    __slots__ = ['consultant']

    def __init__(self, consultant: SupportGetAttribute) -> None:
        self.consultant = consultant

    def visit_Name(self, node: ast.Name) -> TypeIns:
        name_option = self.consultant.getattribute(node.id, node)
        assert isinstance(name_option, Option)
        res = name_option.value
        if not isinstance(res, TypeType):
            raise ParseError()
        return res

    def visit_Attribute(self, node: ast.Attribute) -> TypeIns:
        res = self.visit(node.value)
        assert isinstance(res, TypeType)
        attr_option = res.getattribute(node.attr, node)
        attr_res = attr_option.value
        if not isinstance(attr_res, TypeType):
            raise ParseError()
        return attr_res

    def visit_Subscript(self, node: ast.Subscript) -> TypeIns:
        left_ins = self.visit(node.value)
        assert isinstance(left_ins, TypeIns)

        return left_ins
