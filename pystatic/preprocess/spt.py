import ast
from collections import deque
from typing import Deque
from pystatic.exprparse import ExprParser, eval_expr
from pystatic.typesys import TypeIns, TypeType
from pystatic.visitor import NoGenVisitor
from pystatic.predefined import TypeVarIns, typevar_type, typevar_temp
from pystatic.target import BlockTarget
from pystatic.preprocess.prepinfo import PrepEnvironment, PrepInfo


def resolve_spt(target: 'BlockTarget', env: PrepEnvironment):
    init_prepinfo = env.get_target_prepinfo(target)
    assert init_prepinfo

    queue: Deque['PrepInfo'] = deque()
    queue.append(init_prepinfo)
    while len(queue) > 0:
        cur_prepinfo = queue.popleft()
        for typevar_def in cur_prepinfo.typevar_def.values():
            value = typevar_def.defnode.value
            # TODO: change assert to recoverable error
            assert value, "TypeVar definition shouldn't be empty"
            fill_typevar(value, typevar_def.typevar, cur_prepinfo)

        for typealias_def in cur_prepinfo.type_alias.values():
            value = typealias_def.defnode.value
            typealias = typealias_def.value
            # TODO: change assert to
            assert value, "TypeAlias definition shouldn't be empty"
            # TODO: add warning
            typetype = eval_expr(value, cur_prepinfo).value
            assert isinstance(typetype, TypeType)
            typealias.bindlist = typetype.bindlist

        for clsdef in cur_prepinfo.cls_def.values():
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
    class TypeVarFillerComplete(Exception):
        pass

    def __init__(self, typevar: 'TypeVarIns', prepinfo: 'PrepInfo') -> None:
        super().__init__(prepinfo, False)
        self.typevar = typevar
        self.outermost = True

    def accept(self, node: ast.AST):
        try:
            self.visit(node)
            # TODO: change this to recoverable error
            raise ValueError("node is not a TypeVar")
        except self.TypeVarFillerComplete:
            return self.typevar

    def visit_Call(self, node: ast.Call) -> TypeIns:
        if self.outermost:
            self.outermost = False
            applyargs = self.generate_applyargs(node)
            self.outermost = True
            call_option = typevar_type.call(applyargs)
            assert isinstance(call_option.value, TypeVarIns)
            copy_typevar(call_option.value, self.typevar)
            raise self.TypeVarFillerComplete()
        else:
            return super().visit_Call(node)


class TypeAliasFiller(NoGenVisitor):
    pass
