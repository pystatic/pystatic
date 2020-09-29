import ast
from pystatic.arg import Argument
from pystatic.message import MessageBox
from pystatic.typesys import *
from pystatic.infer.visitor import BaseVisitor
from pystatic.infer.checker import TypeChecker
from pystatic.infer.recorder import SymbolRecorder


class ValueParser(BaseVisitor):
    def __init__(self, mbox: MessageBox, recorder: SymbolRecorder):
        self.mbox = mbox
        self.checker = TypeChecker(self.mbox)
        self.recorder = recorder


class RValueParser(ValueParser):
    def __init__(self, mbox: MessageBox, recorder):
        super().__init__(mbox, recorder)

    def accept(self, node) -> Optional[TypeIns]:
        return self.visit(node)

    def lookup_var(self, name):
        cur_type = self.recorder.cur_type
        if self.recorder.is_defined(name):
            return cur_type.lookup_local_var(name)
        else:
            return cur_type.lookup_var(name)

    def visit_Name(self, node):
        tp = self.lookup_var(node.id)
        if not tp:
            self.mbox.add_err(node, f"unresolved reference '{node.id}'")
        return tp

    def visit_Attribute(self, node):
        attr: str = node.attr
        value: Optional[TypeIns] = self.visit(node.value)
        if value is not None:
            tp = value.getattribute(attr)
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
        name = node.func.id
        tp = self.lookup_var(name)
        if not tp:
            self.mbox.add_err(node, f"unresolved reference '{name}'")
            return
        if isinstance(tp, (TypeType, TypeIns)):
            return tp.call()
        else:
            raise Exception(f"todo {type(tp)} of {tp}")
