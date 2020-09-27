import ast
import logging
from pystatic import symtable
from pystatic.target import MethodTarget
from pystatic.preprocess.type_expr import eval_type_expr
from typing import List, TYPE_CHECKING, Optional
from pystatic.typesys import (TypeClassTemp, TypeFuncTemp, TypeModuleTemp,
                              TypeVar, TpState, TypeTemp, any_ins)
from pystatic.visitor import BaseVisitor, NoGenVisitor, VisitorMethodNotFound
from pystatic.preprocess.dependency import DependencyGraph

if TYPE_CHECKING:
    from pystatic.target import BlockTarget
    from pystatic.symtable import SymTable
    from pystatic.preprocess.main import Preprocessor

logger = logging.getLogger(__name__)


def resolve_cls_def(targets: List['BlockTarget']):
    """Get class definition information(inheritance, placeholders)"""
    graph = _build_graph(targets)
    resolve_order = graph.toposort()

    # placeholders
    for temp in resolve_order:
        temp.set_state(TpState.ON)
        _resolve_cls_placeholder(temp)

    # inheritance
    for temp in resolve_order:
        _resolve_cls_inh(temp)
        temp.set_state(TpState.OVER)


def _build_graph(targets: List['BlockTarget']) -> 'DependencyGraph':
    """Build dependency graph"""
    graph = DependencyGraph()
    for target in targets:
        for temp in target.symtable.cls_defs.values():
            assert isinstance(temp, TypeClassTemp)
            _build_graph_cls(temp, graph)
    return graph


def _build_graph_cls(clstemp: 'TypeClassTemp', graph: 'DependencyGraph'):
    """Add dependency relations about a class"""
    inner_sym = clstemp.get_inner_symtable()

    _build_graph_inh(clstemp, graph)

    for subtemp in inner_sym.cls_defs.values():
        assert isinstance(subtemp, TypeClassTemp)
        _build_graph_cls(subtemp, graph)
        # add dependency relations due to containment
        graph.add_dependency(clstemp, subtemp)


def _build_graph_inh(clstemp: 'TypeClassTemp', graph: 'DependencyGraph'):
    """Add dependency relations that due to the inheritance"""
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
    """Resolve placeholders of a class"""
    assert _check_cls_state(clstemp)
    symtable = clstemp.get_def_symtable()
    visitor = _TypeVarVisitor(symtable, [])
    defnode = clstemp.get_defnode()
    for base_node in defnode.bases:
        visitor.accept(base_node)

    clstemp.placeholders = visitor.typevars


def _resolve_cls_inh(clstemp: 'TypeClassTemp'):
    """Resolve baseclasses of a class"""
    assert _check_cls_state(clstemp)
    symtable = clstemp.get_def_symtable()
    defnode = clstemp.get_defnode()

    for base_node in defnode.bases:
        res_type = eval_type_expr(base_node, symtable)
        if res_type:
            clstemp.add_base(res_type)


class _FirstClassTempVisitor(NoGenVisitor):
    """Get the first class template.

    Used to build dependency graph. For example class C inherits A.B,
    this should return A's template so you can add edge from C to A.
    """
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
            return res.temp.get_inner_typedef(node.attr).get_default_type()
        else:
            return res

    def visit_Subscript(self, node: ast.Subscript):
        return self.visit(node.value)


class _TypeVarVisitor(BaseVisitor):
    """Get the list of TypeVar from baseclass nodes.

    Used to generate correct placeholders.
    """
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


def resolve_cls_method(symtable: 'SymTable', uri: str, worker: 'Preprocessor'):
    # uri here is not set correctly
    for tp_temp in symtable.cls_defs.values():
        mt = _resolve_cls_method(uri, tp_temp.get_inner_symtable(), tp_temp)
        if mt:
            worker.process_block(mt, False)

    for tp_temp in symtable.cls_defs.values():
        new_uri = '.'.join([uri, tp_temp.basename])
        resolve_cls_method(tp_temp.get_inner_symtable(), new_uri, worker)


def _resolve_cls_method(uri: str, symtable: 'SymTable',
                        clstemp: 'TypeClassTemp'):
    targets = []
    for method_name in symtable.functions:
        entry = symtable.lookup_local_entry(method_name)
        func = symtable.lookup_local(method_name).temp
        assert isinstance(func, TypeFuncTemp)
        symtb = func.get_inner_symtable()
        ast_node = entry.get_defnode()
        assert isinstance(ast_node, ast.FunctionDef)
        method_uri = '.'.join([uri, method_name])
        targets.append(MethodTarget(method_uri, symtb, clstemp, ast_node))
    return targets


def resolve_cls_attr(symtable: 'SymTable'):
    for tp_temp in symtable.cls_defs.values():
        _resolve_cls_attr(tp_temp)
        resolve_cls_attr(tp_temp.get_inner_symtable())


def _resolve_cls_attr(clstemp: 'TypeClassTemp'):
    true_var_attr = {}
    for name, tp_attr in clstemp.var_attr.items():
        # tp_attr is the temporary dict set in definition.py
        typenode = tp_attr.get('node')  # type: ignore
        symtb = tp_attr.get('symtable')  # type: ignore
        assert typenode
        assert symtb
        var_type = eval_type_expr(typenode, symtb)
        if var_type:
            var_ins = var_type.getins()
            true_var_attr[name] = var_ins
            logger.debug(f'add attribute {name}: {var_ins} to {clstemp}')
        else:
            # TODO: warning here
            true_var_attr[name] = any_ins
    clstemp.var_attr = true_var_attr
