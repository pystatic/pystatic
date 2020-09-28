import ast
from pystatic.arg import Argument
from pystatic.message import MessageBox
from pystatic.typesys import *
from pystatic.infer.visitor import BaseVisitor
from pystatic.infer.type_table import VarTree
from pystatic.infer.checker import TypeChecker


class ValueParser(BaseVisitor):
    def __init__(self, mbox: MessageBox,
                 var_tree: VarTree):
        self.mbox = mbox
        self.var_tree = var_tree
        self.checker = TypeChecker(self.mbox)


class LValueParser(ValueParser):
    def __init__(self, mbox: MessageBox, var_tree: VarTree, rtype):
        super().__init__(mbox, var_tree)
        self.single_name_node = False
        self.rtype = rtype

    def accept(self, node: ast.AST) -> TypeIns:
        if isinstance(node, ast.Name):
            self.single_name_node = True
        return self.visit(node)


class RValueParser(ValueParser):
    def __init__(self, mbox: MessageBox, var_tree: VarTree):
        super().__init__(mbox, var_tree)

    def accept(self, node) -> Optional[TypeIns]:
        return self.visit(node)

    def visit_Name(self, node):
        if node.id == "self":
            tp = self.var_tree.upper_class()
            if tp is not None:
                return tp
        tp = self.var_tree.lookup_attr(node.id)
        if not tp:
            self.mbox.add_err(node, f"unresolved reference '{node.id}'")
        return tp

    def visit_Attribute(self, node):
        attr: str = node.attr
        value: Optional[TypeIns] = self.visit(node.value)
        if value is not None:
            tp = value.getattr(attr)
            if tp is None:
                self.mbox.add_err(node, f"{value} has no attr {tp}")
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

    def visit_Constant(self, node: ast.Constant):
        # TODO
        pass

    def check_argument_in_call(self, node: ast.Call, argument: Argument):
        arg_list = argument.args
        param_length = len(node.args)
        arg_length = len(arg_list)
        if param_length > arg_length:
            self.mbox.add_err(node.args[arg_length], f"unexpected argument")
            self.mbox.add_err(node, f"too more argument for '{node.func.id}'")
            node.args = node.args[:arg_length]
        elif param_length < arg_length:
            self.mbox.add_err(node, f"too few argument for '{node.func.id}'")
            arg_list = arg_list[:param_length]

        for param, arg in zip(node.args, arg_list):
            param_tp = self.visit(param)
            arg_tp = arg.ann
            self.checker.check(arg_tp, param_tp, param)

    def visit_Call(self, node: ast.Call):
        # TODO: the action call need a method
        name = node.func.id
        tp = self.var_tree.lookup_attr(name)
        if not tp:
            self.mbox.add_err(node, f"unresolved reference '{name}'")
        if isinstance(tp, TypeType):
            return tp.call()
        else:
            raise Exception(f"todo {type(tp)}")
