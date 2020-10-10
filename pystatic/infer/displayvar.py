from pystatic.infer.visitor import BaseVisitor
import ast

class DisplayVar(BaseVisitor):
    def __init__(self, recorder):
        self.recorder = recorder

    @property
    def cur_type(self):
        return self.recorder.cur_type

    def accept(self, root):
        for var in self.cur_type.get_inner_symtable().local.keys():
            print(var, self.cur_type.get_inner_symtable().local[var].get_type())
        super().visit(root)

    def visit_ClassDef(self, node: ast.ClassDef):
        class_type = self.cur_type.lookup_local_var(node.name)
        self.recorder.enter_cls(class_type)
        print("class", self.cur_type)
        for var in self.cur_type.temp.var_attr.keys():
            print(var, self.cur_type.temp.var_attr[var])
        for var in self.cur_type.temp.get_inner_symtable().local.keys():
            print(var, self.cur_type.temp.get_inner_symtable().local[var].get_type())
        for subnode in node.body:
            self.visit(subnode)
        self.recorder.leave_cls()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        func_type: TypeIns = self.cur_type.lookup_local_var(node.name)
        self.recorder.enter_func(func_type, None)
        print("function", self.cur_type)
        for var in self.cur_type.temp.get_inner_symtable().local.keys():
            print(var, self.cur_type.temp.get_inner_symtable().local[var].get_type())
        for subnode in node.body:
            self.visit(subnode)
        self.recorder.leave_func()