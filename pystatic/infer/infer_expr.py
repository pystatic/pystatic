import contextlib
from typing import Protocol
from pystatic.visitor import NoGenVisitor
from pystatic.infer.util import ApplyArgs, WithAst, GetItemArgs, InsWithAst
from pystatic.predefined import *


class SupportGetAttribute(Protocol):
    def getattribute(self, name: str, node: ast.AST) -> Result["TypeIns"]:
        ...


def infer_expr(
    node: Optional[ast.AST], attr_consultant: SupportGetAttribute, annotation=False
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
        return ExprInferer(attr_consultant, annotation).accept(node)


def infer_expr_ann(node: ast.AST, consultant: SupportGetAttribute, annotation=False):
    result = infer_expr(node, consultant, annotation)
    value = result.value
    if isinstance(value, TypeType):
        result.value = value.getins(result)
    return result


class ExprInferer(NoGenVisitor):
    def __init__(self, consultant: SupportGetAttribute, annotation: bool) -> None:
        """
        @param annotation: whether regard str as type annotation
        """
        self.consultant = consultant
        self.annotation = annotation
        self.errors = []
        self.in_subs = False
        self.container = None

        self.tmp_var = []  # temporary variables, used for comprehension and lambda

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

    def add_err(self, errcode: ErrorCode):
        self.errors.append(errcode)

    def add_errlist(self, errlist: Optional[List[ErrorCode]]):
        if errlist:
            self.errors.extend(errlist)

    def add_to_container(self, item, node: ast.AST):
        """If under subscript node, then will add item to current container"""
        if self.in_subs:
            self.container.append(WithAst(item, node))

    @contextlib.contextmanager
    def new_scope(self):
        self.tmp_var.append({})
        yield
        self.tmp_var.pop()

    def _add_new_var(self, name: str, tp: TypeIns):
        self.tmp_var[-1][name] = tp

    def _assign(self, target: ast.AST, tp: TypeIns):
        # mainly used for comprehension and lambda expression
        # TODO: support more complex expression
        if isinstance(target, ast.Name):
            self._add_new_var(target.id, tp)
        elif isinstance(target, ast.Tuple):
            if tp.temp == tuple_temp:
                if len(target.elts) > len(tp.bindlist):
                    self.add_err(
                        TooMoreValuesToUnpack(
                            target, len(tp.bindlist), len(target.elts)
                        )
                    )
                elif len(target.elts) < len(tp.bindlist):
                    self.add_err(
                        NeedMoreValuesToUnpack(
                            target, len(tp.bindlist), len(target.elts)
                        )
                    )
                else:
                    for target_node, ins in zip(target.elts, tp.bindlist):
                        if isinstance(target_node, ast.Name):
                            self._add_new_var(target_node.id, ins)

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
            if not kwargnode.arg:
                # **kwargs
                applyargs.varkwarg = WithAst(argins, kwargnode.value)
            else:
                applyargs.add_kwarg(kwargnode.arg, argins, kwargnode.value)
        return applyargs

    def visit_Expr(self, node: ast.Expr):
        return self.visit(node.value)

    def visit_Name(self, node: ast.Name) -> TypeIns:
        for cur_scope in reversed(self.tmp_var):
            if (name_ins := cur_scope.get(node.id)) :
                break
        else:
            name_result = self.consultant.getattribute(node.id, node)
            assert isinstance(name_result, Result)
            assert isinstance(name_result.value, TypeIns)
            self.add_errlist(name_result.errors)
            name_ins = name_result.value

        self.add_to_container(name_ins, node)
        return name_ins

    def visit_Constant(self, node: ast.Constant) -> TypeIns:
        res = None
        if node.value is None:
            res = none_ins
        elif node.value is ...:
            res = ellipsis_ins
        elif self.annotation and isinstance(node.value, str):
            try:
                astnode = ast.parse(node.value, mode="eval")
                result = infer_expr(astnode.body, self.consultant, True)
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

        self.add_errlist(attr_result.errors)

        self.add_to_container(attr_result.value, node)
        return attr_result.value

    def visit_Call(self, node: ast.Call) -> TypeIns:
        with self.block_container():
            left_ins = self.visit(node.func)
            assert isinstance(left_ins, TypeIns)

            applyargs = self.generate_applyargs(node)
            call_result = left_ins.call(applyargs, node)

            self.add_errlist(call_result.errors)

        self.add_to_container(call_result.value, node)
        return call_result.value

    def visit_UnaryOp(self, node: ast.UnaryOp) -> TypeIns:
        with self.block_container():
            operand_ins = self.visit(node.operand)
        assert isinstance(operand_ins, TypeIns)

        result = operand_ins.unaryop_mgf(type(node.op), node)
        self.add_errlist(result.errors)

        self.add_to_container(result.value, node)
        return result.value

    def visit_BinOp(self, node: ast.BinOp) -> TypeIns:
        with self.block_container():
            left_ins = self.visit(node.left)
            right_ins = self.visit(node.right)
        assert isinstance(left_ins, TypeIns)
        assert isinstance(right_ins, TypeIns)

        result = left_ins.binop_mgf(right_ins, type(node.op), node)
        self.add_errlist(result.errors)

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
        self.add_errlist(result.errors)
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
        # assume slice node's value is slice_ins
        self.add_to_container(slice_ins, node)
        return slice_ins

    def visit_Index(self, node: ast.Index):
        return self.visit(node.value)

    def visit_Compare(self, node: ast.Compare):
        with self.block_container():
            left_ins = self.visit(node.left)
            assert isinstance(left_ins, TypeIns)

            for comparator, op in zip(node.comparators, node.ops):
                comparator_ins = self.visit(comparator)
                assert isinstance(comparator_ins, TypeIns)

                result = left_ins.binop_mgf(comparator_ins, type(op), node)  # type: ignore
                self.add_errlist(result.errors)
                left_ins = result.value

        # assert that left_ins is bool type?
        self.add_to_container(bool_ins, node)
        return bool_ins

    def visit_Lambda(self, node: ast.Lambda):
        with self.block_container():
            bodyins = self.visit(node.body)
        assert isinstance(bodyins, TypeIns)
        self.add_to_container(bodyins, node)
        return bodyins

    def visit_BoolOp(self, node: ast.BoolOp):
        # TODO: make this more accurate
        with self.block_container():
            cur_ins = self.visit(node.values[0])
        self.add_to_container(cur_ins, node)
        return cur_ins

    def cope_comprehension(self, node: ast.comprehension):
        with self.block_container():
            iter_ins = self.visit(node.iter)
            assert isinstance(iter_ins, TypeIns)
            iter_type = get_iter_type(iter_ins)
            if not iter_type:
                if iter_ins != any_ins:
                    self.add_err(NotIterable(node.iter, iter_ins))
                iter_type = any_ins
            self._assign(node.target, iter_type)

    def visit_ListComp(self, node: ast.ListComp):
        with self.block_container():
            with self.new_scope():
                for gen in node.generators:
                    assert isinstance(gen, ast.comprehension)
                    self.cope_comprehension(gen)
                item_ins = self.visit(node.elt)
                listins = list_temp.getins([item_ins]).value
        self.add_to_container(listins, node)
        return listins

    def visit_DictComp(self, node: ast.DictComp):
        # TODO finish this
        dict_ins = dict_type.get_default_ins()
        self.add_to_container(dict_ins, node)
        return dict_ins

    def visit_Starred(self, node: ast.Starred):
        # FIXME: fix this
        # TODO: make this more accurate
        self.add_to_container(any_ins, node)
        return any_ins

    def visit_JoinedStr(self, node: ast.JoinedStr):
        self.add_to_container(str_ins, node)
        return str_ins

    def visit_Yield(self, node: ast.Yield):
        # TODO: fix this
        return any_ins

    def visit_IfExp(self, node: ast.IfExp):
        # TODO: fix this
        return self.visit(node.body)


def get_iter_type(itertype: TypeIns) -> Optional[TypeIns]:
    iter_res = itertype.try_getattribute("__next__")
    if iter_res and iter_res.temp == func_temp:
        assert isinstance(iter_res, TypeFuncIns)
        return iter_res.get_ret_type()

    iter_res = itertype.try_getattribute("__iter__")
    if iter_res and iter_res.temp == func_temp:
        assert isinstance(iter_res, TypeFuncIns)
        iterable_ins = iter_res.get_ret_type()
        next_res = iterable_ins.try_getattribute("__next__")
        if next_res and next_res.temp == func_temp:
            assert isinstance(next_res, TypeFuncIns)
            return next_res.get_ret_type()

    return None
