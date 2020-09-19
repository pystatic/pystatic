import ast
import logging
from typing import Optional
from pystatic.typesys import *
from pystatic.typesys import TypeModuleTemp
from pystatic.env import Environment
from pystatic.op_map import *
from pystatic.type_table import VarTree

logger = logging.getLogger(__name__)


class BaseVisitor(object):
    def visit(self, node):
        """Visit a node."""
        method = 'visit_' + node.__class__.__name__
        visitor = getattr(self, method, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node):
        """Called if no explicit visitor function exists for a node."""
        for field, value in ast.iter_fields(node):
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.AST):
                        self.visit(item)
            elif isinstance(value, ast.AST):
                self.visit(value)


class TypeChecker:
    def __init__(self):
        pass

    def check(self, tp1: TypeIns, tp2: TypeIns) -> bool:
        return tp1.__str__() == tp2.__str__()


class ValueParser(BaseVisitor):
    def __init__(self, node, module: TypeModuleTemp, env: Environment,
                 var_tree: VarTree):
        self.node = node
        self.module = module
        self.env = env
        self.var_tree = var_tree

    def accept(self) -> Optional[TypeIns]:
        return self.visit(self.node)

    def visit_Name(self, node):
        tp = self.var_tree.lookup_var(node.id)
        if tp is None:
            self.env.add_err(node, f"Variable '{node.id}' undefined!")
        return tp

    def visit_Attribute(self, node):
        attr: str = node.attr
        value: Optional[TypeIns] = self.visit(node.value)
        if value is not None:
            tp = value.getattr(attr)
            if tp is None:
                self.env.add_err(node, f"{value} has no attr {tp}")
            return tp
        return value

    def visit_List(self, node: ast.List):
        tp_list = []
        for subnode in node.elts:
            res = self.visit(subnode)
            tp_list.append(res)
        return tp_list

    def visit_Tuple(self, node: ast.Tuple):
        tp_list = []
        for subnode in node.elts:
            res = self.visit(subnode)
            tp_list.append(res)
        return tuple(tp_list)

    def visit_Subscirbe(self, node: ast.Subscript):
        # TODO
        pass
        # out_list=self.visit(node.value)

    def visit_Constant(self, node: ast.Constant):
        # TODO
        pass

    def visit_Call(self, node: ast.Call):
        tp = self.var_tree.lookup_cls(node.func.id)
        if tp is None:
            self.env.add_err(node, f"class '{node.func.id}' undefined")
        return tp


class InferVisitor(BaseVisitor):
    def __init__(self, node: ast.AST, module: TypeModuleTemp,
                 env: Environment):
        self.cur_module: TypeModuleTemp = module
        self.checker = TypeChecker()
        self.var_tree = VarTree()
        self.env = env
        self.root = node
        self.checker = TypeChecker()

    def infer(self):
        self.visit(self.root)

    def visit_Assign(self, node: ast.Assign):
        rtype: Optional[TypeIns] = ValueParser(node.value, self.cur_module,
                                               self.env, self.var_tree).accept()
        if rtype is None:  # some wrong with rvalue
            return
        for target in node.targets:
            if isinstance(target, ast.Name):
                tp = self.var_tree.lookup_var(target.id)
                if tp is None:  # var appear first time
                    tp = self.cur_module.getattr(target.id)
                    if tp.__str__() == "Any":  # var with annotation
                        self.var_tree.add_var(target.id, rtype)
                    else:
                        self.var_tree.add_var(target.id, tp)
                else:
                    res = self.checker.check(tp, rtype)
                    if not res:
                        self.env.add_err(target, f"expected type \'{tp}\', got \'{rtype}\' instead")

    def visit_AnnAssign(self, node: ast.AnnAssign):
        rtype: Optional[TypeIns] = ValueParser(node.value, self.cur_module,
                                               self.env, self.var_tree).accept()
        if rtype is None:
            return
        target = node.target
        if isinstance(target, ast.Name):
            tp = self.var_tree.lookup_var(target.id)
            if tp is None:  # var appear first time
                tp = self.cur_module.getattr(target.id)
                self.var_tree.add_var(target.id, tp)
            res = self.checker.check(tp, rtype)
            if not res:
                self.env.add_err(target, f"expected type \'{tp}\', got \'{rtype}\' instead")

    def visit_ClassDef(self, node: ast.ClassDef):
        class_type = self.cur_module.getattr(node.name)
        self.var_tree.add_cls(node.name, class_type)


class InferStarter:
    def __init__(self, sources):
        self.sources = sources

    def start_infer(self):
        for target in self.sources:
            logger.info(f'Type infer in module \'{target.uri}\'')
            mod_uri = target.uri.replace('.', '/')
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
