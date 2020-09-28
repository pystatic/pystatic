import ast
from typing import Set
from enum import Enum
from pystatic.typesys import *


class ScopeType(Enum):
    GLOBAL_TYPE = 0
    LOCAL_TYPE = 1
    NON_LOCAL_TYPE = 2
    CLASS_TYPE = 3
    VAR_TYPE = 4


class Scope:
    def __init__(self, name: str, tp: Union[TypeType, TypeTemp], scope_type: ScopeType):
        self.name = name
        self.tp = tp
        self.scope_type = scope_type

        self.recorded_symbol: Set[str] = set()

    def add_symbol(self, name: str):
        self.recorded_symbol.add(name)

    def is_defined(self, name) -> bool:
        return name in self.recorded_symbol

    def get_attr(self, name, bindlist=None):
        if isinstance(self.tp, TypeType):
            return self.tp.getattribute(name)
        elif isinstance(self.tp, TypeTemp):
            return self.tp.getattribute(name=name, bindlist=bindlist, context=None)

    def set_attr(self, name: str, tp: TypeIns):
        self.tp.setattr(name, tp)


class VarTree:
    def __init__(self, module: TypeModuleTemp):
        self.root = Scope(module.name, module, ScopeType.GLOBAL_TYPE)
        self.stack: List[Scope] = [self.root]
        self.in_func = False

    @property
    def upper_class(self):
        for scope in reversed(self.stack):
            if scope.scope_type == ScopeType.CLASS_TYPE:
                return scope

    def add_symbol(self, name):
        self.stack[-1].add_symbol(name)

    def enter_cls(self, name, tp):
        scope = Scope(name, tp, ScopeType.CLASS_TYPE)
        self.stack.append(scope)

    def leave_cls(self):
        self.stack.pop()

    def enter_func(self, name, tp):
        if self.in_func:
            scope = Scope(name, tp, ScopeType.NON_LOCAL_TYPE)
        else:
            scope = Scope(name, tp, ScopeType.LOCAL_TYPE)
            self.in_func = True
        self.stack.append(scope)

    def leave_func(self):
        self.stack.pop()

    def lookup_attr(self, name):
        if self.is_defined_in_cur_scope(name):
            return self.stack[-1].get_attr(name)
        else:
            for scope in self.stack[::-1][1:]:
                tp = scope.get_attr(name)
                if tp:
                    return tp
        return None

    def set_attr(self, name, tp):
        self.stack[-1].set_attr(name, tp)

    def is_defined_in_cur_scope(self, name):
        return self.stack[-1].is_defined(name)
