import ast
from collections import deque
from typing import Deque
from pystatic.exprparse import ExprParser, eval_expr
from pystatic.typesys import TypeIns, TypeType
from pystatic.visitor import NoGenVisitor
from pystatic.evalutil import ApplyArgs
from pystatic.predefined import TypeVarIns, typevar_type, typevar_temp
from pystatic.preprocess.prepinfo import PrepEnvironment, PrepInfo


def resolve_typevar(prepinfo: 'PrepInfo', env: PrepEnvironment):
    pass


def resolve_spt(prepinfo: 'PrepInfo', env: PrepEnvironment):
    assert prepinfo

    queue: Deque['PrepInfo'] = deque()
    queue.append(prepinfo)
    while len(queue) > 0:
        cur_prepinfo = queue.popleft()
        for typevar_name in cur_prepinfo.typevar:
            typevar_def = cur_prepinfo.local[typevar_name]
            assign_node = typevar_def.defnode.value  # right part of assignment
            typevar = typevar_def.value
            # TODO: change assert to recoverable error
            assert assign_node, "TypeVar definition shouldn't be empty"
            assert isinstance(typevar, TypeVarIns)
            fill_typevar(assign_node, typevar, cur_prepinfo)

        for typealias_name in cur_prepinfo.type_alias:
            typealias_def = cur_prepinfo.local[typealias_name]
            typealias = typealias_def.value
            assign_node = typealias_def.defnode.value
            # expression in the right assignment mustn't a string literal
            assert assign_node, "TypeAlias definition shouldn't be empty"
            assert not isinstance(assign_node, ast.Constant)
            # TODO: add warning
            typetype = eval_expr(assign_node, cur_prepinfo,
                                 annotation=True).value
            assert isinstance(typetype, TypeType)
            typealias.bindlist = typetype.bindlist

        for clsdef in cur_prepinfo.cls.values():
            queue.append(clsdef.prepinfo)


def fill_typevar(node: ast.AST, typevar: 'TypeVarIns', prepinfo: 'PrepInfo'):
    TypeVarFiller(typevar, prepinfo).accept(node)


def copy_typevar(src: 'TypeVarIns', dst: 'TypeVarIns'):
    assert src.temp is typevar_temp
    assert dst.temp is typevar_temp
    dst.bindlist = src.bindlist
    dst.kind = src.kind
    dst.bound = src.bound
    dst.constraints = src.constraints


class TypeVarFiller(ExprParser):
    def __init__(self, typevar: 'TypeVarIns', prepinfo: 'PrepInfo') -> None:
        super().__init__(prepinfo, False, False)
        self.typevar = typevar
        self.outermost = True

    def generate_applyargs(self, node: ast.Call) -> ApplyArgs:
        # TODO: warning here for failing.
        applyargs = ApplyArgs()
        name_node = node.args[0]
        name_ins = self.visit(name_node)
        assert name_ins
        applyargs.add_arg(name_ins, name_node)

        # When eval TypeVar's argument can be type represented by
        # a string
        self.annotation = True
        for constrain_node in node.args[1:]:
            argins = self.visit(constrain_node)
            assert isinstance(argins, TypeIns)
            applyargs.add_arg(argins, constrain_node)

        for kwargnode in node.keywords:
            argins = self.visit(kwargnode.value)
            assert isinstance(argins, TypeIns)
            assert kwargnode.arg, "**kwargs is not supported yet"
            applyargs.add_kwarg(kwargnode.arg, argins, kwargnode)
        self.annotation = False
        return applyargs

    def visit_Call(self, node: ast.Call) -> TypeIns:
        if self.outermost:
            self.outermost = False
            applyargs = self.generate_applyargs(node)
            self.outermost = True
            call_option = typevar_type.call(applyargs)
            assert isinstance(call_option.value, TypeVarIns)
            copy_typevar(call_option.value, self.typevar)
            return self.typevar
        else:
            return super().visit_Call(node)


class TypeAliasFiller(NoGenVisitor):
    pass
