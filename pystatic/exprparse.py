import ast
from pystatic.typesys import *
from pystatic.message import MessageBox
from pystatic.infer.checker import TypeChecker
from pystatic.infer.visitor import BaseVisitor
from pystatic.infer import op_map
from pystatic.arg import Argument, Arg


class ExprParser(BaseVisitor):
    def __init__(self, mbox: MessageBox, recorder):
        self.mbox = mbox
        self.recorder = recorder
        self.checker = TypeChecker(self.mbox)

    def parse_expr(self, node):
        print(ast.dump(node))
        return self.visit(node)

    def type_consistent(self, tp1, tp2):
        return self.checker.check(tp1, tp2)

    def lookup_var(self, name):
        tp = self.recorder.lookup_local(name)
        if tp:
            return tp
        cur_type = self.recorder.cur_type
        if self.recorder.is_defined(name):
            return cur_type.lookup_local_var(name)
        else:
            return cur_type.lookup_var(name)

    def visit_Attribute(self, node: ast.Attribute):
        attr: str = node.attr
        value = self.visit(node.value)
        if value is not None:
            tp = value.getattribute(attr)
            if tp is None:
                self.mbox.no_attribute(node, value, attr)
            return tp
        return value

    def visit_BinOp(self, node: ast.BinOp):
        print(ast.dump(node))
        left_type = self.visit(node.left)
        if left_type is None:
            return None
        right_type = self.visit(node.right)
        if right_type is None:
            return None
        func_name = op_map.binop_map[type(node.op)]
        func_type = left_type.getattribute(func_name)
        operand = op_map.binop_char_map[type(node.op)]
        if not func_type:
            self.mbox.unsupported_operand(node, operand, left_type, right_type)
        
        args = Argument()
        args.args.append(Arg(None, right_type))
        argument, ret = func_type.call(args)
        ann = argument.args[1].ann
        
        if not self.type_consistent(ann, right_type):
            self.mbox.unsupported_operand(node, operand, left_type, right_type)
        return ret

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name):
            # get the type by the name
            call_type = self.visit(node.func)
            if not call_type:
                return None
            if isinstance(call_type, TypeType):
                return call_type.call()
            elif isinstance(call_type, TypeIns):
                arg, ret = call_type.call(None)
                return ret
            else:
                raise Exception(f"todo {type(call_type)} of {call_type}")
        # check the args' type in the call
        args_type = []
        for arg in node.args:
            args_type.append(self.visit(arg))
        # TODO: here is according to the class of the type, check the args

    def visit_Constant(self, node: ast.Constant):
        assert type(node.value) is not None
        name = type(node.value).__name__
        return self.lookup_var(name)

    def visit_List(self, node: ast.List):
        type_list = []
        for elt in node.elts:
            type_list.append(super().visit(elt))
        return type_list

    def visit_Name(self, node: ast.Name):
        if node.id == 'self':
            return self.recorder.upper_class
        tp = self.lookup_var(node.id)
        if not tp:
            self.mbox.symbol_undefined(node, node.id)
        return tp

    def visit_Tuple(self, node: ast.Tuple):
        type_list = []
        for elt in node.elts:
            type_list.append(super().visit(elt))
        return tuple(type_list)

        
