import ast
from typing import List
from pystatic.errorcode import SymbolUndefined, NoError, ErrorCode
from pystatic.typesys import any_type


class Scope:
    def __init__(self, tp):
        self.type_map = {}
        self.tp = tp

    def add_type(self, name, tp):
        self.type_map[name] = tp


class FuncScope(Scope):
    def __init__(self, tp, argument):
        super().__init__(tp)
        self.type_map = argument


class ClassScope(Scope):
    def __init__(self, tp):
        super().__init__(tp)


class SymbolRecorder:
    def __init__(self, module):
        # record the appeared symbol in cur scope
        self.stack: List[Scope] = []
        self.stack.append(Scope(module))

    @property
    def cur_scope(self) -> Scope:
        return self.stack[-1]

    def is_defined(self, name):
        return name in self.cur_scope.type_map

    def enter_scope(self, tp):
        self.stack.append(Scope(tp))

    def leave_scope(self):
        self.stack.pop()

    def enter_func(self, tp, args):
        self.stack.append(FuncScope(tp, args))

    def leave_func(self):
        self.leave_scope()

    def enter_cls(self, tp):
        self.stack.append(ClassScope(tp))

    def leave_cls(self):
        self.leave_scope()

    def add_type(self, name, tp):
        self.cur_scope.add_type(name, tp)

    @property
    def upper_class(self):
        for scope in self.stack[::-1]:
            if isinstance(scope, ClassScope):
                return scope.tp
        return None

    def getattribute(self, name, node: ast.AST = None) -> ErrorCode:
        for scope in self.stack[::-1]:
            tp = scope.type_map.get(name)
            if tp:
                return NoError(tp)
        return SymbolUndefined(any_type, node, name)
