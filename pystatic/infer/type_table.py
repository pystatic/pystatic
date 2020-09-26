import ast
from enum import Enum
from pystatic.typesys import *


class ScopeType(Enum):
    GLOBAL_TYPE = 0
    LOCAL_TYPE = 1
    NON_LOCAL_TYPE = 2
    CLASS_TYPE = 3
    VAR_TYPE = 4


class Scope:
    def __init__(self, name: str, tp: Union[TypeType, TypeTemp], parent: "Scope",
                 scope_type: ScopeType):
        self.name = name
        self.tp = tp
        self.scope_type = scope_type
        self.parent = parent

        self.scopes: Dict[str, Scope] = {}

    def add_scope(self, name: str, scope: "Scope"):
        self.scopes[name] = scope

    def get_attr(self, name: str, bindlist=None):
        if isinstance(self.tp, TypeType):
            return self.tp.getattribute(name=name, context=None)
        elif isinstance(self.tp, TypeTemp):
            return self.tp.getattribute(name=name, bindlist=bindlist, context=None)
        else:
            raise Exception("TODO")

    def set_attr(self, name, tp):
        self.tp.setattr(name, tp)

    def get_cls(self, name):
        scope = self.scopes.get(name)
        assert scope is not None
        assert scope.scope_type == ScopeType.CLASS_TYPE
        return scope

    def get_func(self, name):
        scope = self.scopes.get(name)
        assert scope is not None
        assert scope.scope_type == ScopeType.LOCAL_TYPE or \
               scope.scope_type == ScopeType.NON_LOCAL_TYPE
        return scope

    def is_defined(self, name) -> bool:
        return name in self.scopes


class VarTree:
    def __init__(self, module: TypeModuleTemp):
        self.root = Scope(module.name, module, None, ScopeType.GLOBAL_TYPE)
        self.cur_scope: Scope = self.root
        self.in_func = False

    @property
    def upper_class(self):
        tmp_scope = self.cur_scope
        while tmp_scope:
            if tmp_scope.scope_type == ScopeType.CLASS_TYPE:
                return tmp_scope.tp
            tmp_scope = tmp_scope.parent
        return None

    def add_cls(self, name, tp):
        scope = Scope(name, tp, self.cur_scope, ScopeType.CLASS_TYPE)
        self.cur_scope.add_scope(name, scope)

    def add_var(self, name, tp):
        scope = Scope(name, tp, self.cur_scope, ScopeType.VAR_TYPE)
        self.cur_scope.add_scope(name, scope)
        self.cur_scope.set_attr(name, tp)

    def add_func(self, name, tp):
        if self.in_func:
            scope = Scope(name, tp, self.cur_scope, ScopeType.NON_LOCAL_TYPE)
        else:
            scope = Scope(name, tp, self.cur_scope, ScopeType.LOCAL_TYPE)
        self.cur_scope.add_scope(name, scope)

    def enter_cls(self, name):
        self.cur_scope = self.cur_scope.get_cls(name)

    def leave_cls(self):
        self.cur_scope = self.cur_scope.parent

    def enter_func(self, name):
        self.cur_scope = self.cur_scope.get_func(name)

    def leave_func(self):
        self.leave_cls()

    def lookup_attr(self, name):
        tp = self.cur_scope.get_attr(name)
        if tp:
            return tp
        tmp_scope = self.cur_scope.parent
        while tmp_scope:
            if tmp_scope.scope_type == ScopeType.LOCAL_TYPE \
                    or tmp_scope.scope_type == ScopeType.GLOBAL_TYPE:
                tp = tmp_scope.get_attr(name)
                if tp:
                    return tp
            tmp_scope = tmp_scope.parent
        return None

    def is_defined_in_cur_scope(self, name):
        return self.cur_scope.is_defined(name)
