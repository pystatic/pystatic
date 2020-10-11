from typing import List


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
    def cur_type(self):
        return self.cur_scope.tp

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

    def getattribute(self, name, tp=None):
        if tp:
            return tp
        cur_type = self.cur_type
        if self.is_defined(name):
            return cur_type.lookup_local_var(name)
        else:
            return cur_type.lookup_var(name)
