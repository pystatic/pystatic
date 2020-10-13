import ast
from typing import List, Optional
from pystatic.errorcode import ErrorCode
from pystatic.visitor import NoGenVisitor
from pystatic.message import MessageBox
from pystatic.typesys import TypeIns
from pystatic.apply import ApplyArgs
from pystatic.option import Option


def eval_expr(node: ast.AST,
              attr_consultant,
              mbox: MessageBox,
              is_record: bool = True):
    """
    consultant:
        support getattribute(str, ast.AST) -> Option[TypeIns]

    is_record:
        report error or not.
    """
    return ExprParser(attr_consultant, mbox, is_record).accept(node)


class ExprParser(NoGenVisitor):
    def __init__(self,
                 consultant,
                 mbox: MessageBox,
                 is_record: bool = True) -> None:
        """
        is_record:
            whether report error or not.
        """
        self.consultant = consultant
        self.mbox = mbox
        self.is_record = is_record

    def _add_err(self, errlist: Optional[List[ErrorCode]]):
        if self.is_record and errlist:
            for errorcode in errlist:
                self.mbox.make(errorcode)

    def accept(self, node) -> TypeIns:
        res = self.visit(node)
        assert isinstance(res, TypeIns)
        return res

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
