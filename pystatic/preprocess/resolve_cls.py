import ast
import contextlib
from collections import deque
from typing import Deque, List
from pystatic.target import MethodTarget
from pystatic.typesys import TypeIns, TypeType
from pystatic.predefined import TypeGenericTemp, TypeVarIns, TypeFuncIns
from pystatic.visitor import BaseVisitor
from pystatic.message import MessageBox
from pystatic.symtable import TableScope
from pystatic.arg import Argument
from pystatic.preprocess.resolve_func import resolve_func_template
from pystatic.preprocess.resolve_util import eval_preptype
from pystatic.preprocess.prepinfo import *


def resolve_cls(clsdef: "prep_cls", shallow: bool):
    # resolve super classes
    clstemp = clsdef.clstemp
    mbox = clsdef.def_prepinfo.mbox
    clstemp.baseclass = []
    is_generic = True
    for base_node in clsdef.defnode.bases:
        base_res = eval_preptype(base_node, clsdef.prepinfo, False, shallow)
        res_type = base_res.option_ins.value
        base_res.option_ins.dump_to_box(mbox)
        assert isinstance(res_type, TypeType)

        if res_type:
            res_ins = res_type.get_default_ins()
            is_new = True
            for old_ins in clstemp.baseclass:
                if res_ins.temp == old_ins.temp:
                    is_new = False
                    if not shallow:
                        mbox.add_err(DuplicateBaseclass(base_node))
                    break
            if is_new:
                clstemp.baseclass.append(res_type.get_default_ins())
        is_generic = is_generic or base_res.generic

    if not shallow:
        resolve_cls_placeholder(clsdef, clsdef.def_prepinfo.mbox)

    if not shallow or not is_generic:
        clsdef.stage = PREP_COMPLETE


def resolve_cls_placeholder(clsdef: "prep_cls", mbox: "MessageBox"):
    """Resolve placeholders of a class"""
    clstemp = clsdef.clstemp
    visitor = _TypeVarVisitor(clsdef.prepinfo, mbox)
    for base_node in clsdef.defnode.bases:
        visitor.accept(base_node)

    clstemp.placeholders = visitor.get_typevar_list()


class _TypeVarVisitor(BaseVisitor):
    """Get the list of TypeVar from baseclass nodes.

    Used to generate correct placeholders.
    """

    def __init__(self, prepinfo: "PrepInfo", mbox: "MessageBox") -> None:
        self.prepinfo = prepinfo
        self.typevars: List["TypeVarIns"] = []
        self.generic_tpvars: List["TypeVarIns"] = []
        self.mbox = mbox
        self.in_gen = False

        self.met_gen = False

    def accept(self, node):
        return self.visit(node)

    @contextlib.contextmanager
    def enter_generic(self):
        if self.met_gen:
            # duplicate error has been added in resolve_cls
            yield

        else:
            old_in_gen = self.in_gen

            self.met_gen = True
            self.in_gen = True
            yield
            self.in_gen = old_in_gen

    def get_typevar_list(self) -> List["TypeVarIns"]:
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
        name_result = self.prepinfo.getattribute(node.id, node)
        if isinstance(name_result.value, TypeVarIns):
            self.add_tpvar(name_result.value)
        name_result.dump_to_box(self.mbox)
        return name_result.value

    def visit_Attribute(self, node: ast.Attribute):
        left_value = self.visit(node.value)
        assert isinstance(left_value, TypeIns)
        result = left_value.getattribute(node.attr, node)
        result.dump_to_box(self.mbox)
        res = result.value
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


def resolve_cls_method(
    prepinfo: "PrepInfo", env: "PrepEnvironment", mbox: "MessageBox"
):
    # TODO: symid here is not set correctly
    manager = env.manager
    queue: Deque["PrepInfo"] = deque()
    queue.append(prepinfo)

    while len(queue):
        cur_prepinfo = queue.popleft()
        for clsdef in cur_prepinfo.cls.values():
            method_targets = _resolve_cls_method(clsdef, mbox)
            for blk_target in method_targets:
                # NOTE: here we add the target directly to the queue
                # that get around manager, which may be problematic
                env.add_target_prepinfo(
                    blk_target,
                    PrepMethodInfo(
                        clsdef.clstemp, cur_prepinfo, cur_prepinfo.mbox, env
                    ),
                )
                manager.q_preprocess.append(blk_target)

            for subclsdef in clsdef.prepinfo.cls.values():
                queue.append(subclsdef.prepinfo)


def _resolve_cls_method(clsdef: "prep_cls", mbox: "MessageBox") -> List[MethodTarget]:
    targets = []  # method targets that need to be preprocessed
    clstemp = clsdef.clstemp
    symid = clstemp.name
    symtable = clstemp.get_inner_symtable()

    def get_method_kind(node: ast.FunctionDef):
        """classmethod or staticmethod"""
        is_classmethod = False
        is_staticmethod = False
        for dec_node in node.decorator_list:
            if isinstance(dec_node, ast.Name):
                if dec_node.id == "classmethod":
                    is_classmethod = True

                elif dec_node.id == "staticmethod":
                    is_staticmethod = True
        return is_classmethod, is_staticmethod

    def modify_argument(
        argument: Argument, is_classmethod: bool, is_staticmethod: bool
    ):
        if is_classmethod:
            argument.args[0].ann = clstemp.get_default_typetype()
        elif not is_staticmethod:
            default_ins_result = clstemp.get_default_ins()
            default_ins_result.dump_to_box(mbox)
            argument.args[0].ann = default_ins_result.value

    def add_func_def(
        argument: Argument, ret: TypeIns, node: ast.FunctionDef
    ) -> TypeFuncIns:
        is_classmethod, is_staticmethod = get_method_kind(node)
        modify_argument(argument, is_classmethod, is_staticmethod)

        name = node.name
        inner_symtable = symtable.new_symtable(name, TableScope.FUNC)
        func_ins = TypeFuncIns(name, symtable.glob_symid, inner_symtable, argument, ret)
        # get attribute because of assignment of self
        if not is_staticmethod:
            symtb = func_ins.get_inner_symtable()
            method_symid = ".".join([symid, name])
            targets.append(MethodTarget(method_symid, symtb, clstemp, node, mbox))

        return func_ins

    def add_func_overload(
        ins: TypeFuncIns, args: Argument, ret: TypeIns, node: ast.FunctionDef
    ):
        is_classmethod, is_staticmethod = get_method_kind(node)
        modify_argument(args, is_classmethod, is_staticmethod)
        ins.add_overload(args, ret)

    for func in clsdef.prepinfo.func.values():
        resolve_func_template(func, add_func_def, add_func_overload, mbox)

    return targets
