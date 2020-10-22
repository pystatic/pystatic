import ast
from typing import List, Dict
from pystatic.errorcode import SymbolUndefined, ErrorCode
from pystatic.typesys import TypeIns, TypeType, any_type, TypeFuncIns
from pystatic.option import Option
from pystatic.symtable import SymTable


class Scope:
    def __init__(self, tp: TypeIns):
        self.type_map: Dict[str, TypeIns] = {}
        self.tp = tp
        self.buffer: Dict[str, TypeIns] = {}

    def set_type(self, name: str, tp: TypeIns):
        self.type_map[name] = tp

    def add_buffer(self, name, tp):
        old_tp = self.type_map[name]
        self.type_map[name] = tp
        self.buffer[name] = old_tp

    def release_buffer(self, name):
        self.type_map[name] = self.buffer[name]


class FuncScope(Scope):
    def __init__(self, tp: TypeIns, args: Dict[str, TypeIns],
                 ret_annotation: TypeIns):
        super().__init__(tp)
        self.type_map = args
        self.ret_annotation = ret_annotation
        self.ret_type: List[TypeIns] = []


class ClassScope(Scope):
    def __init__(self, tp: TypeIns):
        super().__init__(tp)


class ModuleScope(Scope):
    def __init__(self, tp: TypeIns):
        super().__init__(tp)


class SymbolRecorder:
    """record the appeared symbol in cur scope"""

    def __init__(self, module):
        self.stack: List[Scope] = []
        self.stack.append(ModuleScope(module))

    @property
    def cur_scope(self) -> Scope:
        return self.stack[-1]

    def is_defined(self, name: str):
        return name in self.cur_scope.type_map

    def enter_scope(self, tp: TypeIns):
        self.stack.append(Scope(tp))

    def leave_scope(self):
        self.stack.pop()

    def enter_func(self, tp: TypeIns, args: Dict[str, TypeIns], ret_annotation):
        self.stack.append(FuncScope(tp, args, ret_annotation))

    def leave_func(self):
        self.leave_scope()

    def enter_cls(self, tp: TypeIns):
        self.stack.append(ClassScope(tp))

    def leave_cls(self):
        self.leave_scope()

    def add_ret(self, ret_type: TypeIns):
        cur_scope = self.cur_scope
        assert isinstance(cur_scope, FuncScope)
        cur_scope.ret_type.append(ret_type)

    def get_ret_annotation(self):
        cur_scope = self.cur_scope
        assert isinstance(cur_scope, FuncScope)
        return cur_scope.ret_annotation

    def set_type(self, name: str, tp: TypeIns):
        self.cur_scope.set_type(name, tp)

    def add_buffer(self, name, tp):
        self.cur_scope.add_buffer(name, tp)

    def release_buffer(self, name):
        self.cur_scope.release_buffer(name)

    def get_comment_type(self, name) -> TypeIns:
        scope = self.cur_scope
        table: SymTable = scope.tp.get_inner_symtable()
        tp = table.legb_lookup(name)
        # if isinstance(scope.tp, TypeFuncIns):
        #     print(table.local)
        if tp:
            return tp
        assert False, f"undefined {name}"

    def get_run_time_type(self, name):
        tp = self.cur_scope.type_map.get(name)
        if tp:
            return tp
        for scope in self.stack[::-1][1:]:
            tp = scope.type_map.get(name)
            if tp:
                return tp
            else:
                if isinstance(scope, (FuncScope, ModuleScope)):
                    table: SymTable = scope.tp.get_inner_symtable()
                    tp = table.lookup_local(name)
                if tp:
                    return tp
        return tp

    def getattribute(self, name, node: ast.AST) -> Option:
        tp = self.get_run_time_type(name)
        if name=="self":
            print(tp.getattribute("hj", None).value)
        if tp:
            return Option(tp)
        else:
            option: Option = Option(any_type)
            option.add_err(SymbolUndefined(node, name))
            return option
