"""
Resolve class related type information.
"""

import ast
import logging
from pystatic.target import MethodTarget
from pystatic.preprocess.def_expr import (eval_argument_type, eval_return_type,
                                          eval_type_def_expr,
                                          template_resolve_fun)
from typing import List, TYPE_CHECKING, Optional
from pystatic.typesys import (TypeClassTemp, TypeFuncIns, TypeModuleTemp,
                              TypeVarTemp, TpState, TypeTemp, any_ins, TypeIns,
                              TypeVarIns, TypeType)
from pystatic.visitor import BaseVisitor, NoGenVisitor, VisitorMethodNotFound
from pystatic.message import MessageBox
from pystatic.symtable import Entry, TableScope
from pystatic.preprocess.dependency import DependencyGraph
from pystatic.preprocess.sym_util import (add_baseclass, get_cls_defnode,
                                          get_temp_state, set_temp_state)
from pystatic.arg import Argument

if TYPE_CHECKING:
    from pystatic.target import BlockTarget
    from pystatic.symtable import SymTable
    from pystatic.preprocess.main import Preprocessor

logger = logging.getLogger(__name__)


def resolve_cls_def(targets: List['BlockTarget'], mbox: 'MessageBox'):
    """Get class definition information(inheritance, placeholders)"""
    graph = _build_graph(targets)
    resolve_order = graph.toposort()

    # placeholders
    for temp in resolve_order:
        set_temp_state(temp, TpState.ON)
        _resolve_cls_placeholder(temp)

    # inheritance
    for temp in resolve_order:
        _resolve_cls_inh(temp, mbox)
        set_temp_state(temp, TpState.OVER)


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
        defnode = get_cls_defnode(clstemp)

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
    state = get_temp_state(temp)
    return state != TpState.OVER


def _resolve_cls_placeholder(clstemp: 'TypeClassTemp'):
    """Resolve placeholders of a class"""
    assert _check_cls_state(clstemp)
    symtable = clstemp.get_def_symtable()
    visitor = _TypeVarVisitor(symtable, [])
    defnode = get_cls_defnode(clstemp)
    for base_node in defnode.bases:
        visitor.accept(base_node)

    clstemp.placeholders = visitor.typevars


def _resolve_cls_inh(clstemp: 'TypeClassTemp', mbox: 'MessageBox'):
    """Resolve baseclasses of a class"""
    assert _check_cls_state(clstemp)
    symtable = clstemp.get_def_symtable()
    defnode = get_cls_defnode(clstemp)

    for base_node in defnode.bases:
        option_base = eval_type_def_expr(base_node, symtable)
        option_base.dump_to_box(mbox)
        res_type = option_base.value
        assert isinstance(res_type, TypeType)
        if res_type:
            add_baseclass(clstemp, res_type)


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
            return res.temp.get_inner_typedef(node.attr).get_default_typetype()
        else:
            return res

    def visit_Subscript(self, node: ast.Subscript):
        return self.visit(node.value)


class _TypeVarVisitor(BaseVisitor):
    """Get the list of TypeVar from baseclass nodes.

    Used to generate correct placeholders.
    """
    def __init__(self, symtable: 'SymTable',
                 typevars: List['TypeVarIns']) -> None:
        self.symtable = symtable
        self.typevars = typevars

    def visit_Name(self, node: ast.Name):
        curtype = self.symtable.lookup(node.id)
        if curtype and isinstance(curtype, TypeVarIns):
            if curtype not in self.typevars:
                self.typevars.append(curtype)

    def visit_Attribute(self, node: ast.Attribute):
        assert False, "not implemented yet"

    def visit_Subscript(self, node: ast.Subscript):
        self.visit(node.slice)


def resolve_cls_method(symtable: 'SymTable', uri: str, worker: 'Preprocessor',
                       mbox: 'MessageBox'):
    # uri here is not set correctly
    for tp_temp in symtable._cls_defs.values():
        mt = _resolve_cls_method(uri, tp_temp, mbox)
        if mt:
            worker.process_block(mt, False)

    for tp_temp in symtable._cls_defs.values():
        new_uri = '.'.join([uri, tp_temp.basename])
        resolve_cls_method(tp_temp.get_inner_symtable(), new_uri, worker, mbox)


def _resolve_cls_method(uri: str, clstemp: 'TypeClassTemp',
                        mbox: 'MessageBox'):
    targets = []
    new_fun_defs = {}
    symtable = clstemp.get_inner_symtable()

    def get_method_kind(node: ast.FunctionDef):
        """classmethod or staticmethod"""
        is_classmethod = False
        is_staticmethod = False
        for dec_node in node.decorator_list:
            if isinstance(dec_node, ast.Name):
                if dec_node.id == 'classmethod':
                    is_classmethod = True

                elif dec_node.id == 'staticmethod':
                    is_staticmethod = True
        return is_classmethod, is_staticmethod

    def modify_argument(argument: Argument, is_classmethod: bool,
                        is_staticmethod: bool):
        if is_classmethod:
            argument.args[0].ann = clstemp.get_default_typetype()
        elif not is_staticmethod:
            argument.args[0].ann = clstemp.get_default_ins()

    def add_def(node: ast.FunctionDef) -> TypeFuncIns:
        nonlocal symtable, new_fun_defs, mbox
        option_argument = eval_argument_type(node.args, symtable)
        option_return = eval_return_type(node.returns, symtable)

        option_argument.dump_to_box(mbox)
        option_return.dump_to_box(mbox)

        argument = option_argument.value
        ret_ins = option_return.value

        name = node.name
        is_classmethod, is_staticmethod = get_method_kind(node)
        modify_argument(argument, is_classmethod, is_staticmethod)

        inner_symtable = symtable.new_symtable(name, TableScope.FUNC)
        func_ins = TypeFuncIns(name, symtable.glob_uri, inner_symtable,
                               argument, ret_ins)
        symtable.add_entry(name, Entry(func_ins, node))
        new_fun_defs[name] = func_ins

        # get attribute because of assignment of self
        if not is_staticmethod:
            symtb = func_ins.get_inner_symtable()
            method_uri = '.'.join([uri, name])
            targets.append(MethodTarget(method_uri, symtb, clstemp, node))

        logger.debug(f'({symtable.uri}) {name}: {func_ins}')
        return func_ins

    def add_overload(ins: TypeFuncIns, args: Argument, ret: TypeIns,
                     node: ast.FunctionDef):
        is_classmethod, is_staticmethod = get_method_kind(node)
        modify_argument(args, is_classmethod, is_staticmethod)
        ins.add_overload(args, ret)
        logger.debug(
            f'overload ({symtable.uri}) {node.name}: {ins.str_expr(None)}')

    template_resolve_fun(symtable, add_def, add_overload, mbox)
    symtable._func_defs = new_fun_defs

    return targets


def resolve_cls_attr(symtable: 'SymTable', mbox: 'MessageBox'):
    for tp_temp in symtable._cls_defs.values():
        _resolve_cls_attr(tp_temp, mbox)
        resolve_cls_attr(tp_temp.get_inner_symtable(), mbox)


def _resolve_cls_attr(clstemp: 'TypeClassTemp', mbox: 'MessageBox'):
    true_var_attr = {}
    for name, tp_attr in clstemp.var_attr.items():
        # tp_attr is the temporary dict set in definition.py
        typenode = tp_attr.get('node')  # type: ignore
        symtb = tp_attr.get('symtable')  # type: ignore
        assert typenode
        assert symtb
        option_var = eval_type_def_expr(typenode, symtb)
        var_ins = option_var.value

        option_var.dump_to_box(mbox)

        true_var_attr[name] = var_ins
        logger.debug(
            f'add attribute {name}: {var_ins} to {clstemp.str_expr(None)}')
    clstemp.var_attr = true_var_attr
