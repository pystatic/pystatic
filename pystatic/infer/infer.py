import ast
import logging
from typing import Optional
from pystatic.typesys import *
from pystatic.typesys import TypeModuleTemp
from pystatic.infer.op_map import *
from pystatic.infer.checker import TypeChecker
from pystatic.infer.visitor import BaseVisitor
from pystatic.message import MessageBox
from pystatic.infer.recorder import SymbolRecorder
from pystatic.infer.exprparse import ExprParse

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class InferVisitor(BaseVisitor):
    def __init__(self,
                 node: ast.AST,
                 module: TypeModuleTemp,
                 mbox: MessageBox):
        self.cur_module: TypeModuleTemp = module
        self.root = node
        self.mbox: MessageBox = mbox
        self.checker = TypeChecker(self.mbox)

        self.recorder = SymbolRecorder(module)

        self.ret_list = []
        self.ret_annotation = None

    def infer(self):
        self.visit(self.root)

    @property
    def cur_type(self):
        return self.recorder.cur_type

    def type_consistent(self, ltype, rtype):
        return self.checker.check(ltype, rtype)

    def visit_Assign(self, node: ast.Assign):
        rtype = ExprParse(self.mbox, self.recorder).parse_expr(node.value)
        if rtype is None:  # some wrong with rvalue
            return
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.infer_name_node_of_assign(target, node.value, rtype)
            elif isinstance(target, (ast.List, ast.Tuple)):
                self.check_multi_left_of_assign(target.elts, node.value, rtype)
            else:
                self.check_composed_node_of_assign(target, node.value, rtype)

    def infer_name_node_of_assign(self, target, rnode, rtype):
        if self.recorder.is_defined(target.id):
            ltype = self.cur_type.lookup_local_var(target.id)
        else:  # var appear first time
            self.recorder.add_symbol(target.id)
            ltype = self.cur_type.lookup_local_var(target.id)
            if ltype.__str__() == "Any":  # var with no annotation
                self.cur_type.setattr(target.id, rtype)
        if not self.type_consistent(ltype, rtype):
            self.mbox.incompatible_type_in_assign(rnode, ltype, rtype)

    def check_composed_node_of_assign(self, target, rnode, rtype):
        ltype = ExprParse(self.mbox, self.recorder).parse_expr(target)
        if not ltype:
            return
        if not self.type_consistent(ltype, rtype):
            self.mbox.incompatible_type_in_assign(rnode, ltype, rtype)

    def check_multi_left_of_assign(self, target, rnode, rtypes):
        if len(target) < len(rtypes):
            self.mbox.need_more_values_to_unpack(rnode)
        elif len(target) > len(rtypes):
            self.mbox.too_more_values_to_unpack(rnode)
        for lvalue, node, rtype in zip(target, rnode.elts, rtypes):
            if isinstance(lvalue, ast.Name):
                self.infer_name_node_of_assign(lvalue, node, rtype)
            elif isinstance(lvalue, (ast.List, ast.Tuple)):
                self.check_multi_left_of_assign(lvalue.elts, node, rtype)
            else:
                self.check_composed_node_of_assign(lvalue, node, rtype)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        rtype: Optional[TypeIns] = ExprParse(self.mbox, self.recorder).parse_expr(node.value)
        if rtype is None:
            return
        target = node.target
        if isinstance(target, ast.Name):
            self.check_name_node_of_annassign(target, node.value, rtype)
        else:
            self.check_composed_node_of_assign(target, node.value, rtype)

    def check_name_node_of_annassign(self, target, rnode, rtype):
        if not self.recorder.is_defined(target.id):  # var appear first time
            self.recorder.add_symbol(target.id)
        ltype = self.cur_type.lookup_local_var(target.id)
        if not self.type_consistent(ltype, rtype):
            self.mbox.incompatible_type_in_assign(rnode, ltype, rtype)

    def check_composed_node_of_annassign(self, target, rnode, rtype):
        self.check_composed_node_of_assign(target, rnode, rtype)

    def visit_AugAssign(self):



    def visit_ClassDef(self, node: ast.ClassDef):
        self.recorder.add_symbol(node.name)
        class_type = self.cur_type.lookup_local_var(node.name)
        self.recorder.enter_scope(class_type)
        for subnode in node.body:
            self.visit(subnode)
        self.recorder.leave_scope()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.recorder.add_symbol(node.name)
        func_type: TypeIns = self.cur_module.lookup_local_var(node.name)
        self.ret_annotation = func_type.call(None)  # TODO: need modify on overload func
        self.recorder.enter_scope(func_type)
        for subnode in node.body:
            self.visit(subnode)
        self.infer_ret_value_of_func(func_type, node.returns)
        self.recorder.leave_scope()

    def infer_ret_value_of_func(self, func_type, type_comment):
        if len(self.ret_list) == 0:
            rtype = none_type
            if not self.checker.is_any(self.ret_annotation):
                self.mbox.return_value_expected(type_comment)
        elif len(self.ret_list) == 1:
            # TODO
            rtype = self.ret_list[0]
            if rtype is None:
                rtype = none_type
        else:
            # TODO
            pass
        self.ret_list = []
        if not self.checker.is_any(self.ret_annotation):
            func_type.ret_type = rtype

    def visit_Return(self, node: ast.Return):
        ret_type = ExprParse(self.mbox, self.recorder).parse_expr(node.value)
        self.check_ret_type(self.ret_annotation, node, ret_type)
        self.ret_list.append(ret_type)

    def check_ret_type(self, annotation, ret_node: ast.Return, ret_type):
        if ret_type is None:
            self.mbox.return_value_expected(ret_node)
            return
        if not self.checker.check(annotation, ret_type):
            self.mbox.incompatible_return_type(ret_node.value, annotation, ret_type)

    def visit_While(self, node: ast.While):
        k = 0
        self.visit(node.test)
        for subnode in node.body:
            k += 1
            if isinstance(subnode, ast.Break):
                break
            self.visit(subnode)
        if k < len(node.body):
            self.mbox.add_err(node.body[k], f"This code is unreachable")


class InferStarter:
    def __init__(self, sources, mbox):
        self.sources = sources
        self.mbox = mbox

    def start_infer(self):
        for uri, target in self.sources.items():
            logger.info(f'Type infer in module \'{uri}\'')
            # tp = target.module_temp.lookup_local_var('f1')
            # print(tp.temp.ret)
            infer_visitor = InferVisitor(target.ast, target.module_temp, self.mbox)
            infer_visitor.infer()
