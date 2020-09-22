import ast
import logging
from typing import Optional
from pystatic.typesys import *
from pystatic.typesys import TypeModuleTemp
from pystatic.env import Environment
from pystatic.infer.op_map import *
from pystatic.infer.type_table import VarTree
from pystatic.infer.checker import TypeChecker
from pystatic.infer.visitor import BaseVisitor
from pystatic.infer.value_parser import LValueParser, RValueParser

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class InferVisitor(BaseVisitor):
    def __init__(self, node: ast.AST, module: TypeModuleTemp,
                 env: Environment):
        self.cur_module: TypeModuleTemp = module
        self.var_tree: VarTree = VarTree(module)
        self.env = env
        self.root = node
        self.checker = TypeChecker(self.env)

    def infer(self):
        self.visit(self.root)

    def check_type_consistent(self, ltype, rtype, node):
        self.checker.check(ltype, rtype, node)

    def visit_Assign(self, node: ast.Assign):
        rtype: Optional[TypeIns] = RValueParser(node.value, self.env, self.var_tree).accept()
        if rtype is None:  # some wrong with rvalue
            return
        for target in node.targets:
            if isinstance(target, ast.Name):
                ltype = self.handle_name_node_of_assign(target, rtype)
                self.check_type_consistent(ltype, rtype, target)

    def handle_name_node_of_assign(self, target, rtype) -> TypeIns:
        if self.var_tree.is_defined(target.id):
            tp = self.var_tree.lookup_attr(target.id)
            return tp
        else:  # var appear first time
            tp = self.var_tree.lookup_attr(target.id)
            if tp.__str__() == "Any":  # var with no annotation
                self.var_tree.add_var(target.id, rtype)
            else:
                self.var_tree.add_var(target.id, tp)
            return tp

    def visit_AnnAssign(self, node: ast.AnnAssign):
        rtype: Optional[TypeIns] = RValueParser(node.value, self.env, self.var_tree).accept()
        if rtype is None:
            return
        target = node.target
        if isinstance(target, ast.Name):
            ltype = self.handle_name_node_of_ann_assign(target)
            self.check_type_consistent(ltype, rtype, target)

    def handle_name_node_of_ann_assign(self, target) -> TypeIns:
        tp = self.var_tree.lookup_attr(target.id)
        if not self.var_tree.is_defined(target.id):  # var appear first time
            tp = self.var_tree.lookup_attr(target.id)
            self.var_tree.add_var(target.id, tp)
        return tp

    def visit_ClassDef(self, node: ast.ClassDef):
        class_type = self.var_tree.lookup_attr(node.name)

        self.var_tree.add_cls(node.name, class_type)
        self.var_tree.enter_cls(node.name)
        for subnode in node.body:
            self.visit(subnode)
        self.var_tree.leave_cls()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        func_type = self.var_tree.lookup_attr(node.name)
        self.infer_ret_value_of_func(node, func_type)
        self.var_tree.add_func(node.name, func_type)

    def infer_ret_value_of_func(self, node, func_type):
        rtype = FunctionDefVisitor(self.env, self.var_tree).accept(node)

        if func_type.ret_type.__str__() == "Any":
            pass


class FunctionDefVisitor(BaseVisitor):
    def __init__(self, env, var_tree):
        self.env = env
        self.var_tree = var_tree
        self.type_list = []

    def accept(self, node):
        assert isinstance(node, ast.FunctionDef)
        self.visit(node)


    def visit_Return(self, node: ast.Return):
        tp = RValueParser(node.value, self.env, self.var_tree)
        if tp not in self.type_list:
            self.type_list.append(tp)

    class InferStarter:
        def __init__(self, sources):
            self.sources = sources

        def start_infer(self):
            for uri, target in self.sources.items():
                logger.info(f'Type infer in module \'{uri}\'')
                mod_uri = uri.replace('.', '/')
                mod_uri += ".py"
                try:
                    with open(mod_uri) as f:
                        data = f.read()
                except FileNotFoundError:
                    logger.error(f'file \'{mod_uri}\' not found')
                    continue
                node = ast.parse(data)
                infer_visitor = InferVisitor(node, target.module, target.env)
                infer_visitor.infer()
