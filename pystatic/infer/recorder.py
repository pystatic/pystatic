import ast
from typing import List, Dict
from pystatic.errorcode import SymbolUndefined, ErrorCode
from pystatic.typesys import TypeIns, TypeType, any_type
from pystatic.option import Option


class Scope:
    def __init__(self, tp: TypeIns):
        self.type_map: Dict[str, TypeIns] = {}
        self.tp = tp

    def set_type(self, name: str, tp: TypeIns):
        self.type_map[name] = tp


class FuncScope(Scope):
    def __init__(self, tp: TypeIns, argument: Dict[str, TypeIns]):
        super().__init__(tp)
        self.type_map = argument


class ClassScope(Scope):
    def __init__(self, tp: TypeIns):
        super().__init__(tp)


class SymbolRecorder:
    def __init__(self, module):
        # record the appeared symbol in cur scope
        self.stack: List[Scope] = []
        self.stack.append(Scope(module))

    @property
    def cur_scope(self) -> Scope:
        return self.stack[-1]

    def is_defined(self, name: str):
        return name in self.cur_scope.type_map

    def enter_scope(self, tp: TypeType):
        self.stack.append(Scope(tp))

    def leave_scope(self):
        self.stack.pop()

    def enter_func(self, tp: TypeIns, args: Dict[str, TypeIns]):
        self.stack.append(FuncScope(tp, args))

    def leave_func(self):
        self.leave_scope()

    def enter_cls(self, tp: TypeIns):
        self.stack.append(ClassScope(tp))

    def leave_cls(self):
        self.leave_scope()

    def set_type(self, name: str, tp: TypeIns):
        self.cur_scope.set_type(name, tp)

    def getattribute(self, name, node: ast.AST) -> Option:
        tp = self.cur_scope.type_map.get(name)
        if tp:
            return Option(tp)
        for scope in self.stack[::-1][1:]:
            tp = scope.type_map.get(name)
            if tp:
                return Option(tp)
            else:
                tp = scope.tp.get_local_symbol(name)
                if tp:
                    return Option(tp)
        option = Option(any_type)
        option.add_err(SymbolUndefined(node, name))
        return option
