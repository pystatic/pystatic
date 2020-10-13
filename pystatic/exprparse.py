import ast
from typing import List, Optional, Protocol
from pystatic.errorcode import ErrorCode
from pystatic.visitor import NoGenVisitor
from pystatic.message import MessageBox
from pystatic.typesys import TypeIns
from pystatic.apply import ApplyArgs
from pystatic.option import Option


class SupportGetAttribute(Protocol):
    def getattribute(self, name: str,
                     node: Optional[ast.AST]) -> Option['TypeIns']:
        ...


def eval_expr(node: Optional[ast.AST], attr_consultant: SupportGetAttribute):
    """
    consultant:
        support getattribute(str, ast.AST) -> Option[TypeIns]

    is_record:
        report error or not.
    """
    return ExprParser(attr_consultant).accept(node)


class ExprParser(NoGenVisitor):
    def __init__(self, consultant: SupportGetAttribute) -> None:
        """
        is_record:
            whether report error or not.
        """
        self.consultant = consultant
        self.errors = []

    def _add_err(self, errlist: Optional[List[ErrorCode]]):
        if errlist:
            self.errors.extend(errlist)

    def accept(self, node) -> Option[TypeIns]:
        self.errors = []
        tpins = self.visit(node)
        assert isinstance(tpins, TypeIns)
        option_res = Option(tpins)
        option_res.add_errlist(self.errors)
        return option_res

    def visit_Name(self, node: ast.Name) -> TypeIns:
        name_option = self.consultant.getattribute(node.id, node)
        assert isinstance(name_option, Option)
        assert isinstance(name_option.value, TypeIns)

        self._add_err(name_option.errors)
        return name_option.value

    def visit_Attribute(self, node: ast.Attribute) -> TypeIns:
        res = self.visit(node.value)
        assert isinstance(res, TypeIns)
        attr_option = res.getattribute(node.attr, node)

        self._add_err(attr_option.errors)

        return attr_option.value

    def visit_Call(self, node: ast.Call) -> TypeIns:
        left_ins = self.visit(node.func)
        assert isinstance(left_ins, TypeIns)

        applyargs = ApplyArgs()
        # generate applyargs
        for argnode in node.args:
            argins = self.visit(argnode)
            assert isinstance(argins, TypeIns)
            applyargs.add_arg(argins, argnode)
        for kwargnode in node.keywords:
            argins = self.visit(kwargnode.value)
            assert isinstance(argins, TypeIns)
            assert kwargnode.arg, "**kwargs is not supported now"
            applyargs.add_kwarg(kwargnode.arg, argins, kwargnode)

        call_option = left_ins.call(applyargs)

        self._add_err(call_option.errors)

        return call_option.value
