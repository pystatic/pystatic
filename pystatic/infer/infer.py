import ast
import logging
from typing import Optional
from pystatic.typesys import *
from pystatic.typesys import TypeModuleTemp
from pystatic.infer.op_map import *
from pystatic.infer.type_table import VarTree
from pystatic.infer.checker import TypeChecker
from pystatic.infer.visitor import BaseVisitor
from pystatic.message import MessageBox
from pystatic.infer.value_parser import LValueParser, RValueParser

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class InferVisitor(BaseVisitor):
    def __init__(self, node: ast.AST, module: TypeModuleTemp,
                 mbox: MessageBox):
        self.cur_module: TypeModuleTemp = module
        self.var_tree: VarTree = VarTree(module)
        self.root = node
        self.mbox = mbox
        self.checker = TypeChecker(self.mbox)

        self.ret_value = []
        self.ret_annotation = None
        self.imported_symbol = set()

    def infer(self):
        self.visit(self.root)

    def check_type_consistent(self, ltype, rtype, node):
        self.checker.check(ltype, rtype, node)

    def visit_Assign(self, node: ast.Assign):
        rtype: Optional[TypeIns] = RValueParser(self.mbox, self.var_tree).accept(node.value)
        if rtype is None:  # some wrong with rvalue
            return
        for target in node.targets:
            if isinstance(target, ast.Name):
                ltype = self.handle_name_node_of_assign(target, rtype)
                self.check_type_consistent(ltype, rtype, target)
            elif isinstance(target, ast.Tuple):
                 if len(target.elts)!=len(rtype):


    def handle_name_node_of_assign(self, target, rtype) -> TypeIns:
        if self.var_tree.is_defined_in_cur_scope(target.id):
            tp = self.var_tree.lookup_attr(target.id)
            return tp
        else:  # var appear first time
            self.var_tree.add_symbol(target.id)
            tp = self.var_tree.lookup_attr(target.id)
            if tp.__str__() == "Any":  # var with no annotation
                self.var_tree.set_attr(target.id, rtype)
            return tp

    def visit_AnnAssign(self, node: ast.AnnAssign):
        rtype: Optional[TypeIns] = RValueParser(self.mbox, self.var_tree).accept(node.value)
        if rtype is None:
            return
        target = node.target
        if isinstance(target, ast.Name):
            ltype = self.handle_name_node_of_ann_assign(target)
            self.check_type_consistent(ltype, rtype, target)

    def handle_name_node_of_ann_assign(self, target) -> TypeIns:
        if not self.var_tree.is_defined_in_cur_scope(target.id):  # var appear first time
            self.var_tree.add_symbol(target.id)
        tp = self.var_tree.lookup_attr(target.id)
        return tp

    def visit_ClassDef(self, node: ast.ClassDef):
        self.var_tree.add_symbol(node.name)
        class_type = self.var_tree.lookup_attr(node.name)
        self.var_tree.enter_cls(node.name, class_type)
        for subnode in node.body:
            self.visit(subnode)
        self.var_tree.leave_cls()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.var_tree.add_symbol(node.name)
        func_type = self.var_tree.lookup_attr(node.name)
        self.var_tree.enter_func(node.name, func_type)
        for subnode in node.body:
            self.visit(subnode)
        # self.infer_ret_value_of_func(node, func_type)
        self.var_tree.leave_func()

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
        tp = RValueParser(self.mbox, self.var_tree).accept(node.value)
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
            md = target.module_temp
            t = target.module_temp.getattribute('A', None, None)
            # print(t.call())
            print(t)
            print(type(target.module_temp.getattribute('A', None, None)))

            infer_visitor = InferVisitor(target.ast, target.module_temp, self.mbox)
            infer_visitor.infer()
