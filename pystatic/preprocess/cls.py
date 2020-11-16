import ast
import contextlib
from collections import deque
from pystatic.target import MethodTarget
from pystatic.preprocess.def_expr import (eval_argument_type, eval_return_type,
                                          eval_typedef_expr,
                                          template_resolve_fun)
from typing import Deque, List, TYPE_CHECKING
from pystatic.typesys import (TypeClassTemp, TypeIns, TypeType)
from pystatic.predefined import (TypeGenericTemp, TypeModuleTemp, TypeVarIns,
                                 TypeFuncIns)
from pystatic.exprparse import eval_expr
from pystatic.visitor import BaseVisitor, NoGenVisitor, VisitorMethodNotFound
from pystatic.message import MessageBox
from pystatic.symtable import TableScope
from pystatic.arg import Argument
from pystatic.preprocess.dependency import DependencyGraph
from pystatic.preprocess.util import add_baseclass
from pystatic.preprocess.prepinfo import *

if TYPE_CHECKING:
    from pystatic.target import BlockTarget


def resolve_cls_dependency(targets: List['BlockTarget'],
                           env: 'PrepEnvironment'):
    """Resolve dependencies between classes"""
    graph = DependencyGraph()
    for target in targets:
        prepinfo = env.get_target_prepinfo(target)
        assert prepinfo
        for clsdef in prepinfo.cls_def.values():
            assert isinstance(clsdef.clstemp, TypeClassTemp)
            build_dependency_graph(clsdef, graph, prepinfo)

    return graph.toposort()


def build_dependency_graph(clsdef: 'prep_clsdef', graph: 'DependencyGraph',
                           prepinfo: 'PrepInfo'):
    """Add dependency relations about a class"""
    build_inheritance_graph(clsdef, prepinfo, graph)

    # build dependencies of classes defined inside this class
    for subclsdef in clsdef.prepinfo.cls_def.values():
        build_dependency_graph(subclsdef, graph, prepinfo)
        # add dependency relations due to containment
        graph.add_dependency(clsdef, subclsdef)


def build_inheritance_graph(clsdef: 'prep_clsdef', prepinfo: 'PrepInfo',
                            graph: 'DependencyGraph'):
    """Add dependency relations that due to the inheritance"""
    clstemp = clsdef.clstemp
    graph.add_clsdef(clsdef)
    assert isinstance(
        clstemp, TypeClassTemp) and not isinstance(clstemp, TypeModuleTemp)
    defnode = clsdef.defnode

    visitor = _FirstClassTempVisitor(prepinfo)
    for basenode in defnode.bases:
        inh_clsdef = visitor.accept(basenode)
        if inh_clsdef:
            assert isinstance(inh_clsdef, prep_clsdef)
            graph.add_dependency(clsdef, inh_clsdef)


def resolve_cls_placeholder(clsdef: 'prep_clsdef', mbox: 'MessageBox'):
    """Resolve placeholders of a class"""
    clstemp = clsdef.clstemp
    visitor = _TypeVarVisitor(clsdef.prepinfo, mbox)
    for base_node in clsdef.defnode.bases:
        visitor.accept(base_node)

    clstemp.placeholders = visitor.get_typevar_list()


def resolve_cls_inheritence(clsdef: 'prep_clsdef', mbox: 'MessageBox'):
    """Resolve baseclasses of a class"""
    clstemp = clsdef.clstemp
    for base_node in clsdef.defnode.bases:
        base_option = eval_typedef_expr(base_node, clsdef.def_prepinfo, False)
        base_option.dump_to_box(mbox)
        res_type = base_option.value
        assert isinstance(res_type, TypeType)
        if res_type:
            add_baseclass(clstemp, res_type.get_default_ins())


class _FirstClassTempVisitor(NoGenVisitor):
    """Get the first class template.

    Used to build dependency graph. For example class C inherits A.B,
    this should return A's template so you can add edge from C to A.

    If the inherited class has already defined in symtable, then it won't
    return the TypeTemp of that class.
    """
    def __init__(self, prepinfo: 'PrepInfo') -> None:
        self.prepinfo = prepinfo

    def accept(self, node):
        try:
            return self.visit(node)
        except VisitorMethodNotFound:
            return None

    def visit_Name(self, node: ast.Name):
        prep_def = self.prepinfo.get_prep_def(node.id)
        if isinstance(prep_def, prep_impt):
            prep_def = prep_def.value
        if not isinstance(prep_def, prep_clsdef):
            return None
        return prep_def

    def visit_Attribute(self, node: ast.Attribute):
        return self.visit(node.value)

    def visit_Subscript(self, node: ast.Subscript):
        return self.visit(node.value)


class _TypeVarVisitor(BaseVisitor):
    """Get the list of TypeVar from baseclass nodes.

    Used to generate correct placeholders.
    """
    def __init__(self, prepinfo: 'PrepInfo', mbox: 'MessageBox') -> None:
        self.prepinfo = prepinfo
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
        name_option = eval_expr(node, self.prepinfo)
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


def resolve_cls_method(target: 'BlockTarget', env: 'PrepEnvironment',
                       mbox: 'MessageBox'):
    # TODO: symid here is not set correctly
    init_prepinfo = env.get_target_prepinfo(target)
    assert init_prepinfo
    manager = env.manager
    queue: Deque['PrepInfo'] = deque()
    queue.append(init_prepinfo)

    while len(queue):
        cur_prepinfo = queue.popleft()
        for clsdef in cur_prepinfo.cls_def.values():
            method_targets = _resolve_cls_method(clsdef, mbox)
            for blk_target in method_targets:
                # NOTE: here we add the target directly to the queue
                # that get around manager, which may be problematic
                env.add_target_prepinfo(
                    blk_target, MethodPrepInfo(clsdef.clstemp, cur_prepinfo))
                manager.q_preprocess.append(blk_target)

            for subclsdef in clsdef.prepinfo.cls_def.values():
                queue.append(subclsdef.prepinfo)


def _resolve_cls_method(clsdef: 'prep_clsdef',
                        mbox: 'MessageBox') -> List[MethodTarget]:
    targets = []
    prepinfo = clsdef.prepinfo
    clstemp = clsdef.clstemp
    symid = clstemp.name
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

    def add_func_def(node: ast.FunctionDef) -> TypeFuncIns:
        nonlocal prepinfo, mbox
        argument_option = eval_argument_type(node.args, prepinfo)
        return_option = eval_return_type(node.returns, prepinfo)

        argument_option.dump_to_box(mbox)
        return_option.dump_to_box(mbox)

        argument = argument_option.value
        ret_ins = return_option.value

        is_classmethod, is_staticmethod = get_method_kind(node)
        modify_argument(argument, is_classmethod, is_staticmethod)

        name = node.name
        inner_symtable = symtable.new_symtable(name, TableScope.FUNC)
        func_ins = TypeFuncIns(name, symtable.glob_symid, inner_symtable,
                               argument, ret_ins)

        func_entry = prepinfo.func[name]
        func_entry.value = func_ins

        # get attribute because of assignment of self
        if not is_staticmethod:
            symtb = func_ins.get_inner_symtable()
            method_symid = '.'.join([symid, name])
            targets.append(
                MethodTarget(method_symid, symtb, clstemp, node, mbox))

        return func_ins

    def add_func_overload(ins: TypeFuncIns, args: Argument, ret: TypeIns,
                          node: ast.FunctionDef):
        is_classmethod, is_staticmethod = get_method_kind(node)
        modify_argument(args, is_classmethod, is_staticmethod)
        ins.add_overload(args, ret)

    template_resolve_fun(prepinfo, add_func_def, add_func_overload, mbox)

    return targets


def dump_to_symtable(target: 'BlockTarget', env: 'PrepEnvironment'):
    init_prepinfo = env.get_target_prepinfo(target)
    assert init_prepinfo
    queue: Deque[PrepInfo] = deque()
    queue.append(init_prepinfo)

    while len(queue):
        cur_prepinfo = queue.popleft()
        cur_prepinfo.dump()

        for clsdef in cur_prepinfo.cls_def.values():
            queue.append(clsdef.prepinfo)
