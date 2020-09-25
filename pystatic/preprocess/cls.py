import ast
import logging
from pystatic.preprocess.type_expr import eval_type_expr
from typing import List, TYPE_CHECKING, Optional
from pystatic.typesys import (TypeClassTemp, TypeModuleTemp, TypeVar, TpState,
                              TypeTemp)
from pystatic.visitor import BaseVisitor, NoGenVisitor, VisitorMethodNotFound
from pystatic.preprocess.dependency import DependencyGraph

if TYPE_CHECKING:
    from pystatic.manager import Target
    from pystatic.symtable import SymTable

logger = logging.getLogger(__name__)


def resolve_cls_def(targets: List['Target']):
    graph = _build_graph(targets)
    resolve_order = graph.toposort()
    for temp in resolve_order:
        temp.set_state(TpState.ON)
        _resolve_cls_placeholder(temp)
    for temp in resolve_order:
        _resolve_cls_inh(temp)
        temp.set_state(TpState.OVER)


def _build_graph(targets: List['Target']) -> 'DependencyGraph':
    graph = DependencyGraph()
    for target in targets:
        for temp in target.symtable.cls_defs.values():
            assert isinstance(temp, TypeClassTemp)
            _build_graph_cls(temp, graph)
    return graph


def _build_graph_cls(clstemp: 'TypeClassTemp', graph: 'DependencyGraph'):
    inner_sym = clstemp.get_inner_symtable()

    _build_graph_inh(clstemp, graph)

    for subtemp in inner_sym.cls_defs.values():
        assert isinstance(subtemp, TypeClassTemp)
        _build_graph_cls(subtemp, graph)
        graph.add_dependency(clstemp, subtemp)


def _build_graph_inh(clstemp: 'TypeClassTemp', graph: 'DependencyGraph'):
    if _check_cls_state(clstemp):
        graph.add_typetemp(clstemp)
        assert isinstance(
            clstemp, TypeClassTemp) and not isinstance(clstemp, TypeModuleTemp)
        defnode = clstemp.get_defnode()

        def_sym = clstemp.get_def_symtable()
        visitor = _FirstClassTempVisitor(def_sym)
        for basenode in defnode.bases:
            first_temp = visitor.accept(basenode)
            assert isinstance(first_temp, TypeTemp) and not isinstance(
                first_temp, TypeModuleTemp
            )  # FIXME: if the result is a module, warninng here
            if first_temp and _check_cls_state(first_temp):
                assert isinstance(first_temp, TypeClassTemp)
                graph.add_dependency(clstemp, first_temp)


def _check_cls_state(temp: 'TypeTemp'):
    state = temp.get_state()
    return state != TpState.OVER


def _resolve_cls_placeholder(clstemp: 'TypeClassTemp'):
    assert _check_cls_state(clstemp)
    symtable = clstemp.get_def_symtable()
    visitor = _TypeVarVisitor(symtable, [])
    defnode = clstemp.get_defnode()
    for base_node in defnode.bases:
        visitor.accept(base_node)

    clstemp.placeholders = visitor.typevars


def _resolve_cls_inh(clstemp: 'TypeClassTemp'):
    assert _check_cls_state(clstemp)
    symtable = clstemp.get_def_symtable()
    defnode = clstemp.get_defnode()

    for base_node in defnode.bases:
        res_type = eval_type_expr(base_node, symtable)
        if res_type:
            clstemp.add_base(res_type)


class _FirstClassTempVisitor(NoGenVisitor):
    def __init__(self, symtable: 'SymTable') -> None:
        self.symtable = symtable

    def accept(self, node):
        try:
            return self.visit(node).temp
        except VisitorMethodNotFound:
            return None

    def visit_Name(self,
                   node: ast.Name,
                   symtable: Optional['SymTable'] = None):
        symtable = symtable or self.symtable
        entry = symtable.lookup_entry(node.id)
        return entry.get_type()

    def visit_Attribute(self, node: ast.Attribute):
        res = self.visit(node.value)
        if isinstance(res.temp, TypeModuleTemp):
            return res.temp.get_type_def(node.attr).get_default_type()
        else:
            return res

    def visit_Subscript(self, node: ast.Subscript):
        return self.visit(node.value)


class _TypeVarVisitor(BaseVisitor):
    def __init__(self, symtable: 'SymTable',
                 typevars: List['TypeVar']) -> None:
        self.symtable = symtable
        self.typevars = typevars

    def visit_Name(self, node: ast.Name):
        curtype = self.symtable.lookup(node.id)
        if curtype and isinstance(curtype.temp, TypeVar):
            temp = curtype.temp
            if temp not in self.typevars:
                self.typevars.append(temp)

    def visit_Attribute(self, node: ast.Attribute):
        assert 0, "not implemented yet"

    def visit_Subscript(self, node: ast.Subscript):
        self.visit(node.slice)
