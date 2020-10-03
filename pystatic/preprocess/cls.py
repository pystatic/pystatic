"""
Resolve class related type information.
"""

import ast
import logging
import copy
from pystatic.target import MethodTarget
from pystatic.preprocess.type_expr import eval_type_expr, eval_func_type
from typing import List, TYPE_CHECKING, Optional
from pystatic.typesys import (TypeClassTemp, TypeFuncTemp, TypeModuleTemp,
                              TypeVar, TpState, TypeTemp, any_ins, TypeIns)
from pystatic.visitor import BaseVisitor, NoGenVisitor, VisitorMethodNotFound
from pystatic.symtable import Entry
from pystatic.preprocess.dependency import DependencyGraph
from pystatic.preprocess.sym_util import fake_fun_entry
from pystatic.arg import copy_argument

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
        for temp in target.symtable._cls_defs.values():
            assert isinstance(temp, TypeClassTemp)
            _build_graph_cls(temp, graph)
    return graph


def _build_graph_cls(clstemp: 'TypeClassTemp', graph: 'DependencyGraph'):
    """Add dependency relations about a class"""
    inner_sym = clstemp.get_inner_symtable()

    _build_graph_inh(clstemp, graph)

    for subtemp in inner_sym._cls_defs.values():
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
    for tp_temp in symtable._cls_defs.values():
        mt = _resolve_cls_method(uri, tp_temp)
        if mt:
            worker.process_block(mt, False)

    for tp_temp in symtable._cls_defs.values():
        new_uri = '.'.join([uri, tp_temp.basename])
        resolve_cls_method(tp_temp.get_inner_symtable(), new_uri, worker)


def _resolve_cls_method(uri: str, clstemp: 'TypeClassTemp'):
    targets = []
    new_fun_defs = {}
    symtable = clstemp.get_inner_symtable()

    for name, entry in symtable._func_defs.items():  # type: ignore
        entry: 'fake_fun_entry'
        assert isinstance(entry, fake_fun_entry)
        func_node = entry.defnode
        func_temp = eval_func_type(func_node, symtable).temp
        assert isinstance(func_temp, TypeFuncTemp)
        new_fun_defs[name] = func_temp
        func_ins = func_temp.get_default_ins()

        # TODO: warning when classmethod and staticmethod appear together
        is_classmethod = False
        is_staticmethod = False
        for dec_node in func_node.decorator_list:
            if isinstance(dec_node, ast.Name):
                if dec_node.id == 'classmethod':
                    is_classmethod = True
                    # modify the first parameter's type
                    assert func_temp.argument.args, "error not handled yet"
                    func_temp.argument.args[0].ann = clstemp.get_default_type()
                    symtable.add_entry(name, Entry(func_ins, entry.defnode))

                elif dec_node.id == 'staticmethod':
                    is_staticmethod = True
                    symtable.add_entry(name, Entry(func_ins, entry.defnode))

                else:
                    assert False, "not handled yet"

        if not is_classmethod and not is_staticmethod:
            # TODO: warning name collision
            # modify the first parameter's type
            assert func_temp.argument.args, "error not handled yet"
            func_temp.argument.args[0].ann = clstemp.get_default_ins()
            symtable.add_entry(name, Entry(func_ins, entry.defnode))

        if not is_staticmethod:
            # get attribute because of assignment of self
            symtb = func_temp.get_inner_symtable()
            method_uri = '.'.join([uri, name])
            targets.append(
                MethodTarget(method_uri, symtb, clstemp, entry.defnode))

    symtable._func_defs = new_fun_defs

    return targets


def resolve_cls_attr(symtable: 'SymTable'):
    for tp_temp in symtable._cls_defs.values():
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
