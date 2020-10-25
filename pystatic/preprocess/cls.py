"""
Resolve class related type information.
"""

import ast
import contextlib
from pystatic.target import MethodTarget
from pystatic.preprocess.def_expr import (eval_argument_type, eval_return_type,
                                          eval_typedef_expr,
                                          template_resolve_fun)
from typing import List, TYPE_CHECKING, Optional
from pystatic.typesys import (TypeClassTemp, TypeFuncIns, TypeGenericTemp,
                              TypeModuleTemp, TpState, TypeTemp, TypeIns,
                              TypeVarIns, TypeType)
from pystatic.exprparse import eval_expr
from pystatic.visitor import BaseVisitor, NoGenVisitor, VisitorMethodNotFound
from pystatic.message import MessageBox
from pystatic.symtable import Entry, TableScope
from pystatic.preprocess.dependency import DependencyGraph
from pystatic.preprocess.sym_util import (add_baseclass, get_cls_defnode,
                                          get_fake_data, get_temp_state,
                                          set_temp_state)
from pystatic.arg import Argument

if TYPE_CHECKING:
    from pystatic.target import BlockTarget
    from pystatic.symtable import SymTable
    from pystatic.manager import Manager


def resolve_cls_def(targets: List['BlockTarget'], manager: 'Manager'):
    """Get class definition information(inheritance, placeholders)"""
    graph = _build_graph(targets)
    resolve_order = graph.toposort()

    # placeholders
    for temp in resolve_order:
        set_temp_state(temp, TpState.ON)
        temp_mbox = manager.get_mbox_by_symid(temp.module_symid)
        assert temp_mbox, "This should always true because pystatic must have added the mbox before"
        _resolve_cls_placeholder(temp, temp_mbox)

    # inheritance
    for temp in resolve_order:
        temp_mbox = manager.get_mbox_by_symid(temp.module_symid)
        assert temp_mbox, "This should always true because pystatic must have added the mbox before"
        _resolve_cls_inh(temp, temp_mbox)
        set_temp_state(temp, TpState.OVER)


def _build_graph(targets: List['BlockTarget']) -> 'DependencyGraph':
    """Build dependency graph"""
    graph = DependencyGraph()
    for target in targets:
        fake_data = get_fake_data(target.symtable)
        for temp in fake_data.cls_defs.values():
            assert isinstance(temp, TypeClassTemp)
            _build_graph_cls(temp, graph)
    return graph


def _build_graph_cls(clstemp: 'TypeClassTemp', graph: 'DependencyGraph'):
    """Add dependency relations about a class"""
    inner_sym = clstemp.get_inner_symtable()
    fake_data = get_fake_data(inner_sym)

    _build_graph_inh(clstemp, graph)

    for subtemp in fake_data.cls_defs.values():
        assert isinstance(subtemp, TypeClassTemp)
        _build_graph_cls(subtemp, graph)
        # add dependency relations due to containment
        graph.add_dependency(clstemp, subtemp)


def _build_graph_inh(clstemp: 'TypeClassTemp', graph: 'DependencyGraph'):
    """Add dependency relations that due to the inheritance"""
    if get_temp_state(clstemp) != TpState.OVER:
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
            if first_temp:
                assert get_temp_state(clstemp) != TpState.OVER
                assert isinstance(first_temp, TypeTemp)
                if get_temp_state(first_temp) == TpState.ON:
                    assert isinstance(first_temp, TypeClassTemp)
                    graph.add_dependency(clstemp, first_temp)


def _resolve_cls_placeholder(clstemp: 'TypeClassTemp', mbox: 'MessageBox'):
    """Resolve placeholders of a class"""
    assert get_temp_state(clstemp) != TpState.OVER
    symtable = clstemp.get_def_symtable()
    visitor = _TypeVarVisitor(symtable, mbox)
    defnode = get_cls_defnode(clstemp)
    for base_node in defnode.bases:
        visitor.accept(base_node)

    clstemp.placeholders = visitor.get_typevar_list()


def _resolve_cls_inh(clstemp: 'TypeClassTemp', mbox: 'MessageBox'):
    """Resolve baseclasses of a class"""
    assert get_temp_state(clstemp) != TpState.OVER
    symtable = clstemp.get_def_symtable()
    defnode = get_cls_defnode(clstemp)

    for base_node in defnode.bases:
        base_option = eval_typedef_expr(base_node, symtable)
        base_option.dump_to_box(mbox)
        res_type = base_option.value
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
        return symtable.lookup(node.id)

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
    def __init__(self, symtable: 'SymTable', mbox: 'MessageBox') -> None:
        self.symtable = symtable
        self.typevars: List['TypeVarIns'] = []
        self.generic_tpvars: List['TypeVarIns'] = []
        self.mbox = mbox
        self.in_gen = False

        self.met_gen = False

    @contextlib.contextmanager
    def enter_generic(self):
        if self.met_gen:
            # TODO: double Generic Error
            yield

        else:
            old_in_gen = self.in_gen

            self.met_gen = True
            self.in_gen = True
            yield
            self.in_gen = old_in_gen

    def get_typevar_list(self) -> List['TypeVarIns']:
        if self.met_gen:
            for gen in self.typevars:
                if gen not in self.generic_tpvars:
                    # TODO: add error here(not in generic)
                    self.generic_tpvars.append(gen)
            return self.generic_tpvars
        else:
            return self.typevars

    def add_tpvar(self, tpvarins: TypeVarIns):
        if self.in_gen:
            if tpvarins not in self.generic_tpvars:
                self.generic_tpvars.append(tpvarins)
        else:
            if tpvarins not in self.typevars:
                self.typevars.append(tpvarins)

    def visit_Name(self, node: ast.Name):
        name_option = eval_expr(node, self.symtable)
        if isinstance(name_option.value, TypeVarIns):
            self.add_tpvar(name_option.value)
        name_option.dump_to_box(self.mbox)
        return name_option.value

    def visit_Attribute(self, node: ast.Attribute):
        left_value = self.visit(node.value)
        assert isinstance(left_value, TypeIns)
        res_option = left_value.getattribute(node.attr, node)
        res_option.dump_to_box(self.mbox)
        res = res_option.value
        if isinstance(res, TypeVarIns):
            self.add_tpvar(res)
        return res

    def visit_Subscript(self, node: ast.Subscript):
        left_value = self.visit(node.value)
        assert isinstance(left_value, TypeIns)

        if isinstance(left_value.temp, TypeGenericTemp):
            with self.enter_generic():
                self.visit(node.slice)
        else:
            self.visit(node.slice)
        return left_value  # FIXME: bindlist is not set correctly


def resolve_cls_method(symtable: 'SymTable', symid: str, manager: 'Manager',
                       mbox: 'MessageBox'):
    # symid here is not set correctly
    fake_data = get_fake_data(symtable)
    for tp_temp in fake_data.cls_defs.values():
        method_targets = _resolve_cls_method(symid, tp_temp, mbox)
        for blk_target in method_targets:
            manager.preprocess_block(blk_target)

    for tp_temp in fake_data.cls_defs.values():
        new_symid = '.'.join([symid, tp_temp.basename])
        resolve_cls_method(tp_temp.get_inner_symtable(), new_symid, manager,
                           mbox)


def _resolve_cls_method(symid: str, clstemp: 'TypeClassTemp',
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
            default_ins_option = clstemp.get_default_ins()
            default_ins_option.dump_to_box(mbox)
            argument.args[0].ann = default_ins_option.value

    def add_def(node: ast.FunctionDef) -> TypeFuncIns:
        nonlocal symtable, new_fun_defs, mbox
        argument_option = eval_argument_type(node.args, symtable)
        return_option = eval_return_type(node.returns, symtable)

        argument_option.dump_to_box(mbox)
        return_option.dump_to_box(mbox)

        argument = argument_option.value
        ret_ins = return_option.value

        name = node.name
        is_classmethod, is_staticmethod = get_method_kind(node)
        modify_argument(argument, is_classmethod, is_staticmethod)

        inner_symtable = symtable.new_symtable(name, TableScope.FUNC)
        func_ins = TypeFuncIns(name, symtable.glob_symid, inner_symtable,
                               argument, ret_ins)
        symtable.add_entry(name, Entry(func_ins, node))
        new_fun_defs[name] = func_ins

        # get attribute because of assignment of self
        if not is_staticmethod:
            symtb = func_ins.get_inner_symtable()
            method_symid = '.'.join([symid, name])
            targets.append(
                MethodTarget(method_symid, symtb, clstemp, node, mbox))

        return func_ins

    def add_overload(ins: TypeFuncIns, args: Argument, ret: TypeIns,
                     node: ast.FunctionDef):
        is_classmethod, is_staticmethod = get_method_kind(node)
        modify_argument(args, is_classmethod, is_staticmethod)
        ins.add_overload(args, ret)

    template_resolve_fun(symtable, add_def, add_overload, mbox)
    symtable._func_defs = new_fun_defs

    return targets


def resolve_cls_attr(symtable: 'SymTable', mbox: 'MessageBox'):
    fake_data = get_fake_data(symtable)
    for tp_temp in fake_data.cls_defs.values():
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
        var_option = eval_typedef_expr(typenode, symtb)
        var_ins = var_option.value

        var_option.dump_to_box(mbox)

        true_var_attr[name] = var_ins

    clstemp.var_attr = true_var_attr
