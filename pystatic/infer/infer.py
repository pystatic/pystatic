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
        self.mbox = mbox
        self.checker = TypeChecker(self.mbox)

        self.recorder = SymbolRecorder(module)
        self.ret_value = []
        self.ret_annotation = None

    def infer(self):
        self.visit(self.root)

    @property
    def cur_type(self):
        return self.recorder.cur_type

    def check_type_consistent(self, ltype, rtype, node):
        self.checker.check(ltype, rtype, node)

    def visit_Assign(self, node: ast.Assign):
        rtype: Optional[TypeIns] = ExprParse(self.mbox, self.recorder).parse_expr(node.value)
        if rtype is None:  # some wrong with rvalue
            return
        for target in node.targets:
            if isinstance(target, ast.Name):
                ltype = self.handle_name_node_of_assign(target, rtype)
                self.check_type_consistent(ltype, rtype, target)

    def handle_name_node_of_assign(self, target, rtype) -> TypeIns:
        if self.recorder.is_defined(target.id):
            tp = self.cur_type.lookup_local_var(target.id)
            return tp
        else:  # var appear first time
            self.recorder.add_symbol(target.id)
            tp = self.cur_type.lookup_local_var(target.id)
            if tp.__str__() == "Any":  # var with no annotation
                self.cur_type.setattr(target.id, rtype)
            return tp

    def visit_AnnAssign(self, node: ast.AnnAssign):
        rtype: Optional[TypeIns] = ExprParse(self.mbox, self.recorder).parse_expr(node.value)
        if rtype is None:
            return
        target = node.target
        if isinstance(target, ast.Name):
            ltype = self.handle_name_node_of_ann_assign(target)
            self.check_type_consistent(ltype, rtype, target)

    def handle_name_node_of_ann_assign(self, target) -> TypeIns:
        if not self.recorder.is_defined(target.id):  # var appear first time
            self.recorder.add_symbol(target.id)
        tp = self.cur_type.lookup_local_var(target.id)
        return tp

    def visit_ClassDef(self, node: ast.ClassDef):
        self.recorder.add_symbol(node.name)
        class_type = self.cur_type.lookup_local_var(node.name)
        self.recorder.enter_scope(class_type)
        for subnode in node.body:
            self.visit(subnode)
        self.recorder.leave_scope()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.recorder.add_symbol(node.name)
        func_type = self.cur_module.lookup_local_var(node.name)
        self.recorder.enter_scope(func_type)
        for subnode in node.body:
            self.visit(subnode)
        self.recorder.leave_scope()

    def infer_ret_value_of_func(self, node, func_type):
        for subnode in node.body:
            self.visit(subnode)
        if len(self.ret_value) == 0:
            rtype = any_type
            # TODO: type check
        elif len(self.ret_value) == 1:
            rtype = self.ret_value[0]
        else:
            raise Exception(f"todo")
        self.ret_value = []
        if func_type.call():
            func_type.ret_type = rtype

    def visit_Return(self, node: ast.Return):
        tp = ExprParse(self.mbox, self.recorder).parse_expr(node.value)
        self.checker.check(self.ret_annotation, tp, node.value)
        if tp not in self.ret_value:
            self.ret_value.append(tp)

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
            tp=target.module_temp.lookup_local_var('f1')
            # print(tp.temp.ret)
            infer_visitor = InferVisitor(target.ast, target.module_temp, self.mbox)
            infer_visitor.infer()

    def get_external_symbol(self, module: TypeModuleTemp):
        builtin = module.get_inner_symtable().builtins
