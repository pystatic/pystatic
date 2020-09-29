from typing import List


class Scope:
    def __init__(self, tp):
        self.symbol_set = set()
        self.tp = tp

    def add_symbol(self, name):
        self.symbol_set.add(name)


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
        return name in self.cur_scope.symbol_set

    def enter_scope(self, tp):
        self.stack.append(Scope(tp))

    def leave_scope(self):
        self.stack.pop()

    def add_symbol(self, name):
        self.cur_scope.add_symbol(name)
