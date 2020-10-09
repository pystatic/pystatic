import ast
from pystatic.typesys import *
from pystatic.message import MessageBox
from pystatic.infer.checker import TypeChecker
from pystatic.infer.visitor import BaseVisitor
from pystatic.infer import op_map


class ExprParser(BaseVisitor):
    def __init__(self, mbox: MessageBox, recorder):
        self.mbox = mbox
        self.recorder = recorder
        self.checker = TypeChecker(self.mbox)

    def parse_expr(self, node):
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
        argument, ret = func_type.call()
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
        tp = self.lookup_var(node.id)
        if not tp:
            self.mbox.symbol_undefined(node, node.id)
        return tp

    def visit_Tuple(self, node: ast.Tuple):
        type_list = []
        for elt in node.elts:
            type_list.append(super().visit(elt))
        return tuple(type_list)


class DisplayVar(BaseVisitor):
    def __init__(self, module: TypeModuleTemp, ast_rt: ast.AST):
        self.curscope = module
        self.ast_rt = ast_rt
        self.tab = 0

    def accept(self):
        print(" " * self.tab, self.curscope.name)
        self.tab += 4
        print(" " * self.tab, "attribute in this scope")
        for var in self.curscope.var_attr.keys():
            print(" " * self.tab, var, self.curscope.var_attr[var])
        super().visit(self.ast_rt)
        self.tab -= 4

    def visit_ClassDef(self, node: ast.ClassDef):
        self.displayscopeattribute('class', node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.displayscopeattribute('function', node)

    def displayscopeattribute(self, whichtype, node):
        curscopetmp = self.curscope
        self.curscope = self.curscope.getattr(node.name, None)
        print(" " * self.tab, "below is {} scope".format(whichtype))
        if isinstance(node, ast.ClassDef):
            print(" " * self.tab, self.curscope.name)
        else:
            print(" " * self.tab, node.name, self.curscope)
        self.tab += 4
        for var in self.curscope.temp.var_attr.keys():
            print(" " * self.tab, var, self.curscope.temp.var_attr[var])
        for bodynode in node.body:
            super().visit(bodynode)
        self.tab -= 4
        self.curscope = curscopetmp
