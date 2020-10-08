from pystatic.infer.visitor import BaseVisitor
from pystatic.typesys import TypeModuleTemp
from pystatic.message import MessageBox
from pystatic.infer.checker import TypeChecker
from pystatic.typesys import TypeType, TypeIns
import ast


class ExprParse(BaseVisitor):
    def __init__(self, mbox: MessageBox, recorder):
        self.mbox = mbox
        self.recorder = recorder
        self.type_check = TypeChecker(self.mbox)

    def parse_expr(self, node):
        # print('parse_expr')
        # print(ast.dump(node))
        return super().visit(node)

    def lookup_var(self, name):
        cur_type = self.recorder.cur_type
        if self.recorder.is_defined(name):
            return cur_type.lookup_local_var(name)
        else:
            return cur_type.lookup_var(name)

    def visit_Attribute(self, node: ast.Attribute):
        attr_type = super().visit(node)

        attr_type = attr_type.temp.getattr(node.attr)
        return attr_type

    def visit_BinOp(self, node: ast.BinOp):
        lefttype = super().visit(node.left)
        if lefttype == None:  # here 'None', I want a type to represent the error type
            # during processing, a type mismatch is encountered.
            return lefttype
        righttype = super().visit(node.right)
        if righttype == None:
            return righttype
        # xj's handler is used to determine whether these two types can perform this operation
        # if ok, return type
        # else return 
        raise Exception(f"todo")

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name):
            # get the type by the name
            call_type = self.visit(node.func)
            if not call_type:
                return
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
            args_type.append(super().visit(arg))
        # TODO: here is according to the class of the type, check the args

        return call_type

    def visit_Constant(self, node: ast.Constant):
        # what does node.kind mean?
        # this type is builtin's type, so how to build this class
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
