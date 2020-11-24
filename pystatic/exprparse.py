import ast
import contextlib
from typing import List, Optional, Protocol, Sequence
from pystatic.errorcode import ErrorCode
from pystatic.visitor import NoGenVisitor
from pystatic.typesys import TypeIns, any_ins
from pystatic.evalutil import ApplyArgs, WithAst
from pystatic.option import Option
from pystatic.opmap import binop_map, unaryop_map
from pystatic.predefined import *


class SupportGetAttribute(Protocol):
    def getattribute(self, name: str, node: ast.AST) -> Option['TypeIns']:
        ...


def eval_expr(node: ast.AST,
              attr_consultant: SupportGetAttribute,
              explicit=False,
              annotation=False):
    """
    :param explicit: If True, tuples like (1, 2) will return 
    Tuple[Literal[1], Literal[2]], else return Tuple[int]

    :param annotation: If True, strings inside this node is treated
    as forward-reference other than Literal string.
    """
    return ExprParser(attr_consultant, explicit, annotation).accept(node)


class ExprParser(NoGenVisitor):
    def __init__(self, consultant: SupportGetAttribute, explicit: bool,
                 annotation: bool) -> None:
        self.consultant = consultant
        self.explicit = explicit
        self.annotation = annotation
        self.errors = []

        self.in_subs = False  # under a subscription node?
        self.container = []

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

    def add_error(self, errlist: Optional[List[ErrorCode]]):
        if errlist:
            self.errors.extend(errlist)

    def add_to_container(self, item, node: ast.AST):
        """If under subscript node, then will add item to current container"""
        if self.in_subs:
            self.container.append(WithAst(item, node))

    def get_type_from_astlist(self, typeins: Optional[TypeIns],
                              astlist: Sequence[Optional[ast.AST]]) -> TypeIns:
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
            applyargs.add_kwarg(kwargnode.arg, argins, kwargnode)
        return applyargs

    def accept(self, node: ast.AST) -> Option[TypeIns]:
        self.errors = []
        tpins = self.visit(node)
        assert isinstance(tpins, TypeIns)
        res_option = Option(tpins)
        res_option.add_error_list(self.errors)
        return res_option

    def visit_Name(self, node: ast.Name) -> TypeIns:
        name_option = self.consultant.getattribute(node.id, node)
        assert isinstance(name_option, Option)
        assert isinstance(name_option.value, TypeIns)

        self.add_error(name_option.errors)

        self.add_to_container(name_option.value, node)
        return name_option.value

    def visit_Constant(self, node: ast.Constant) -> TypeIns:
        res = None
        if node.value == None:
            res = none_ins
        elif node.value == ...:
            res = ellipsis_ins
        elif self.annotation and isinstance(node.value, str):
            try:
                astnode = ast.parse(node.value, mode='eval')
                res_option = eval_expr(astnode.body, self.consultant,
                                       self.explicit, True)
                # TODO: add warning here
                res = res_option.value
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
        res = self.visit(node.value)
        assert isinstance(res, TypeIns)
        attr_option = res.getattribute(node.attr, node)

        self.add_error(attr_option.errors)

        self.add_to_container(attr_option.value, node)
        return attr_option.value

    def visit_Call(self, node: ast.Call) -> TypeIns:
        left_ins = self.visit(node.func)
        assert isinstance(left_ins, TypeIns)

        applyargs = self.generate_applyargs(node)
        call_option = left_ins.call(applyargs)

        self.add_error(call_option.errors)

        self.add_to_container(call_option.value, node)
        return call_option.value

    def visit_UnaryOp(self, node: ast.UnaryOp) -> TypeIns:
        operand_ins = self.visit(node.operand)
        assert isinstance(operand_ins, TypeIns)

        op = unaryop_map.get(type(node.op))
        assert op, f"{node.op} is not supported now"
        res_option = operand_ins.unaryop_mgf(op, node)

        self.add_error(res_option.errors)

        self.add_to_container(res_option.value, node)
        return res_option.value

    def visit_BinOp(self, node: ast.BinOp) -> TypeIns:
        left_ins = self.visit(node.left)
        right_ins = self.visit(node.right)
        assert isinstance(left_ins, TypeIns)
        assert isinstance(right_ins, TypeIns)

        op = binop_map.get(type(node.op))
        assert op, f"{node.op} is not supported now"
        res_option = left_ins.binop_mgf(right_ins, op, node)

        self.add_error(res_option.errors)

        self.add_to_container(res_option.value, node)
        return res_option.value

    def visit_Subscript(self, node: ast.Subscript) -> TypeIns:
        with self.block_container():
            left_ins = self.visit(node.value)
            assert isinstance(left_ins, TypeIns)

        container = []
        with self.register_container(container):
            items = self.visit(node.slice)
            assert isinstance(items, (list, tuple, TypeIns))

        assert len(container) == 1
        res_option = left_ins.getitem(container[0])

        self.add_to_container(res_option.value, node)
        return res_option.value

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
        self.add_to_container(bool_ins, node)
        return bool_ins
