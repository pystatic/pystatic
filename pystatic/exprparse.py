import ast
import contextlib
from typing import List, Optional, Protocol, Sequence
from pystatic.errorcode import ErrorCode
from pystatic.visitor import NoGenVisitor
from pystatic.typesys import TypeIns, any_ins
from pystatic.evalutil import ApplyArgs, WithAst, GetItemArgs
from pystatic.result import Result
from pystatic.predefined import *


class SupportGetAttribute(Protocol):
    def getattribute(self, name: str, node: ast.AST) -> Result["TypeIns"]:
        ...


def eval_expr(
    node: Optional[ast.AST],
    attr_consultant: SupportGetAttribute,
    explicit=False,
    annotation=False,
):
    """
    @param node: target ast node.

    @param attr_consultant: instance with getattribute method.

    @param explicit: If True, tuples like (1, 2) will return
    Tuple[Literal[1], Literal[2]], else return Tuple[int].

    @param annotation: If True, strings inside this node is treated
    as forward-reference other than Literal string.
    """
    if not node:
        return Result(none_ins)
    else:
        return ExprParser(attr_consultant, explicit, annotation).accept(node)


class ExprParser(NoGenVisitor):
    def __init__(
        self, consultant: SupportGetAttribute, explicit: bool, annotation: bool
    ) -> None:
        """
        @param annotation: whether regard str as type annotation
        """
        self.consultant = consultant
        self.explicit = explicit
        self.annotation = annotation
        self.errors = []
        self.in_subs = False
        self.container = None

    def accept(self, node) -> Result[TypeIns]:
        self.errors = []
        tpins = self.visit(node)
        assert isinstance(tpins, TypeIns)
        result = Result(tpins)
        result.add_err_list(self.errors)
        return result

    @contextlib.contextmanager
    def register_container(self, container: list):
        old_in_subs = self.in_subs
        old_container = self.container

        self.in_subs = True
        self.container = container
        yield
        self.container = old_container
        self.in_subs = old_in_subs

    @contextlib.contextmanager
    def block_container(self):
        old_in_subs = self.in_subs
        self.in_subs = False
        yield
        self.in_subs = old_in_subs

    def add_err(self, errlist: Optional[List[ErrorCode]]):
        if errlist:
            self.errors.extend(errlist)

    def add_to_container(self, item, node: ast.AST):
        """If under subscript node, then will add item to current container"""
        if self.in_subs:
            self.container.append(WithAst(item, node))

    def get_type_from_astlist(
        self, typeins: Optional[TypeIns], astlist: Sequence[Optional[ast.AST]]
    ) -> TypeIns:
        """Get type from a ast node list"""
        for node in astlist:
            if node:
                new_typeins = self.visit(node)
                assert isinstance(new_typeins, TypeIns)
                if isinstance(new_typeins, TypeLiteralIns):
                    new_typeins = new_typeins.get_value_type()

                if not typeins:
                    typeins = new_typeins
                else:
                    if not typeins.equiv(new_typeins):
                        return any_ins
        return typeins or any_ins

    def generate_applyargs(self, node: ast.Call) -> ApplyArgs:
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
            applyargs.add_kwarg(kwargnode.arg, argins, kwargnode.value)
        return applyargs

    def visit_Expr(self, node: ast.Expr):
        return self.visit(node.value)

    def visit_Name(self, node: ast.Name) -> TypeIns:
        name_result = self.consultant.getattribute(node.id, node)
        assert isinstance(name_result, Result)
        assert isinstance(name_result.value, TypeIns)

        self.add_err(name_result.errors)

        self.add_to_container(name_result.value, node)
        return name_result.value

    def visit_Constant(self, node: ast.Constant) -> TypeIns:
        res = None
        if node.value is None:
            res = none_ins
        elif node.value is ...:
            res = ellipsis_ins
        elif self.annotation and isinstance(node.value, str):
            try:
                astnode = ast.parse(node.value, mode="eval")
                result = eval_expr(astnode.body, self.consultant, self.explicit, True)
                # TODO: add warning here
                res = result.value
            except SyntaxError:
                # TODO: add warning here
                res = TypeLiteralIns(node.value)

        if res:
            self.add_to_container(res, node)
            return res
        else:
            tpins = TypeLiteralIns(node.value)
            self.add_to_container(tpins, node)
            return tpins

    def visit_Attribute(self, node: ast.Attribute) -> TypeIns:
        with self.block_container():
            res = self.visit(node.value)
            assert isinstance(res, TypeIns)
        attr_result = res.getattribute(node.attr, node)

        self.add_err(attr_result.errors)

        self.add_to_container(attr_result.value, node)
        return attr_result.value

    def visit_Call(self, node: ast.Call) -> TypeIns:
        left_ins = self.visit(node.func)
        assert isinstance(left_ins, TypeIns)

        applyargs = self.generate_applyargs(node)
        call_result = left_ins.call(applyargs, node)

        self.add_err(call_result.errors)

        self.add_to_container(call_result.value, node)
        return call_result.value

    def visit_UnaryOp(self, node: ast.UnaryOp) -> TypeIns:
        operand_ins = self.visit(node.operand)
        assert isinstance(operand_ins, TypeIns)

        result = operand_ins.unaryop_mgf(type(node.op), node)
        self.add_err(result.errors)

        self.add_to_container(result.value, node)
        return result.value

    def visit_BinOp(self, node: ast.BinOp) -> TypeIns:
        left_ins = self.visit(node.left)
        right_ins = self.visit(node.right)
        assert isinstance(left_ins, TypeIns)
        assert isinstance(right_ins, TypeIns)

        result = left_ins.binop_mgf(right_ins, type(node.op), node)
        self.add_err(result.errors)

        self.add_to_container(result.value, node)
        return result.value

    def visit_Subscript(self, node: ast.Subscript) -> TypeIns:
        with self.block_container():
            left_ins = self.visit(node.value)
            assert isinstance(left_ins, TypeIns)

        old_annotation = self.annotation
        if left_ins.temp == literal_temp:
            self.annotation = False

        container = []
        with self.register_container(container):
            items = self.visit(node.slice)
            assert isinstance(items, (list, tuple, TypeIns))
        assert len(container) == 1
        if isinstance(container[0].value, (list, tuple)):
            itemargs = GetItemArgs(container[0].value, node)
        else:
            itemargs = GetItemArgs([container[0]], node)
        result = left_ins.getitem(itemargs, node)

        self.annotation = old_annotation

        self.add_to_container(result.value, node)
        self.add_err(result.errors)
        return result.value

    def visit_List(self, node: ast.List):
        if self.in_subs:
            lst = []
            with self.register_container(lst):
                for subnode in node.elts:
                    self.visit(subnode)
            self.add_to_container(lst, node)
            return lst
        else:
            inner_type = self.get_type_from_astlist(None, node.elts)
            return list_temp.getins([inner_type]).value

    def visit_Tuple(self, node: ast.Tuple):
        if self.in_subs:
            lst = []
            with self.register_container(lst):
                for subnode in node.elts:
                    self.visit(subnode)
            tp = tuple(lst)
            self.add_to_container(tp, node)
            return tp
        else:
            inner_type_list = []
            for subnode in node.elts:
                typeins = self.visit(subnode)
                assert isinstance(typeins, TypeIns)
                if not self.explicit and isinstance(typeins, TypeLiteralIns):
                    typeins = typeins.get_value_type()
                inner_type_list.append(typeins)
            return tuple_temp.getins(inner_type_list).value

    def visit_Dict(self, node: ast.Dict):
        key_type = self.get_type_from_astlist(None, node.keys)
        value_type = self.get_type_from_astlist(None, node.values)

        res = dict_temp.getins([key_type, value_type]).value
        self.add_to_container(res, node)
        return res

    def visit_Set(self, node: ast.Set):
        set_type = self.get_type_from_astlist(None, node.elts)

        res = set_temp.getins([set_type]).value
        self.add_to_container(res, node)
        return res

    def visit_Slice(self, node: ast.Slice):
        raise NotImplementedError()

    def visit_Index(self, node: ast.Index):
        return self.visit(node.value)

    def visit_Compare(self, node: ast.Compare):
        left_ins = self.visit(node.left)
        assert isinstance(left_ins, TypeIns)

        for comparator, op in zip(node.comparators, node.ops):
            comparator_ins = self.visit(comparator)
            assert isinstance(comparator_ins, TypeIns)

            result = left_ins.binop_mgf(comparator_ins, type(op), node)  # type: ignore
            self.add_err(result.errors)
            left_ins = result.value

        # assert that left_ins is bool type?
        self.add_to_container(bool_ins, node)
        return bool_ins
