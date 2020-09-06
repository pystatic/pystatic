import ast
import enum
from collections import OrderedDict
from typing import Dict, Optional, List
from pystatic.typesys import (TypeClassTemp, TypeModuleTemp, TypeTemp, TypeIns,
                              any_temp, int_temp, float_temp, bool_temp,
                              str_temp, generic_temp, none_temp)
from pystatic.error import ErrHandler


def lookup_type_scope(scope: 'Scope', name) -> Optional[TypeTemp]:
    """Look up an type in a Scope.

    Deprecated, now used to detect errors caused by old code.
    """
    name_list = name.split('.')
    assert len(name_list) == 1
    target = scope.types.get(name_list[0])
    return target


class Scope(object):
    """Scope that obey the LEGB rule"""
    def __init__(self,
                 glob: 'Scope',
                 non_local: Optional['Scope'],
                 builtins: 'Scope',
                 parent: Optional['Scope'] = None):
        self.local: Dict[str, TypeIns] = {}
        self.types: Dict[str, TypeTemp] = {}
        self.glob = glob
        self.non_local = non_local
        self.builtins = builtins
        self.parent = parent
        self.sub_scopes: OrderedDict[str, 'Scope'] = OrderedDict()

    def _lookup_nonlocal_chain(self, func, *args):
        cur_scope: Optional['Scope'] = self.non_local
        while cur_scope is not None:
            res = func(cur_scope, *args)
            if res:
                return res
            cur_scope = cur_scope.parent
        return None

    def _lookup_by_func(self, func, *args):
        """func is excuted according to LEGB rule"""
        res = func(self, *args)
        if res:
            return res
        res = self._lookup_nonlocal_chain(func, *args)
        if res:
            return res
        res = func(self.glob, *args)
        if res:
            return res
        return func(self.builtins, *args)

    def lookup_local_type(self, name: str) -> Optional[TypeTemp]:
        return lookup_type_scope(self, name)

    def lookup_type(self, name: str) -> Optional[TypeTemp]:
        return self._lookup_by_func(Scope.lookup_local_type, name)

    def add_type(self, name: str, tp):
        self.types[name] = tp

    def lookup_local_var(self, name: str) -> Optional[TypeIns]:
        return self.local.get(name)

    def lookup_var(self, name: str) -> Optional[TypeIns]:
        return self._lookup_by_func(Scope.lookup_local_var, name)

    def add_var(self, name: str, tp: TypeIns):
        self.local[name] = tp


class ScopeType(enum.Enum):
    GLOB = 0
    FUNC = 1
    CLASS = 2


class Environment(object):
    """Environment provides several methods to
    organize type scopes and scopes of a module.
    """
    def __init__(self, scope: Scope, module: TypeModuleTemp):
        self.scope_list = [scope]
        self.name_list: List[str] = [module.uri]
        self.scope_type: List[ScopeType] = [ScopeType.GLOB]
        self.scope_temp: List[TypeTemp] = [module]

        self.module = module

        self.base_index = 0
        self.cls_count = 0

        self.current_cls = None

        self.err = ErrHandler(module.uri)

    def add_err(self, node: ast.AST, msg: str):
        self.err.add_err(node, msg)

    @property
    def scope(self):
        return self.scope_list[-1]

    @property
    def base_scope(self):
        """Base scope is the nearest scope that is
        either a global scope or a function scope.
        Base scope is used to find the nonlocal scope
        """
        return self.scope_list[self.base_index]

    @property
    def glob_scope(self):
        return self.scope_list[0]

    @property
    def current_uri(self):
        return '.'.join(self.name_list)

    @property
    def current_cls_temp(self):
        return self.scope_temp[-1]

    @property
    def in_class(self):
        """Whether we are inside a class scope or not"""
        return self.cls_count > 0

    @property
    def in_func(self):
        """ Whether we are inside a function scope or not"""
        return self.base_index != 0

    def lookup_local_type(self, name: str):
        return self.scope.lookup_local_type(name)

    def lookup_type(self, name: str) -> Optional[TypeTemp]:
        return self.scope.lookup_type(name)

    def add_type(self, name: str, tp_temp: TypeTemp):
        """If the current scope is class scope(include module scope), then it
        will also add tp_temp to the cls_attr"""
        base_cls_temp = self.current_cls_temp
        assert isinstance(base_cls_temp, TypeClassTemp)
        base_cls_temp.setattr(name, tp_temp.get_default_type())

        return self.scope.add_type(name, tp_temp)

    def add_var(self, name: str, tp_ins: TypeIns):
        base_cls_temp = self.current_cls_temp
        assert isinstance(base_cls_temp, TypeClassTemp)
        base_cls_temp.setattr(name, tp_ins)

        return self.scope.add_var(name, tp_ins)

    def lookup_local_var(self, name: str):
        return self.scope.lookup_local_var(name)

    def lookup_var(self, name: str) -> Optional[TypeIns]:
        return self.scope.lookup_var(name)

    def get_non_local(self) -> Optional[Scope]:
        if self.in_func:
            return self.base_scope
        else:
            return None

    def _try_add_scope(self, name: str, new_scope: 'Scope'):
        """If scope name doesn't exist, then add a new scope under the current scope"""
        if name not in self.scope.sub_scopes:
            self.scope.sub_scopes[name] = new_scope

    def _enter_scope(self, name: str, new_scope: 'Scope',
                     scope_type: 'ScopeType', cls_temp: TypeClassTemp):
        self._try_add_scope(name, new_scope)
        self.scope_list.append(new_scope)
        self.scope_type.append(scope_type)
        self.scope_temp.append(cls_temp)
        self.name_list.append(name)

    def enter_class(self, name: str) -> Optional[TypeClassTemp]:
        """Enter a class scope"""
        cls_temp = self.lookup_local_type(name)
        if cls_temp:
            assert isinstance(cls_temp, TypeClassTemp)
            self.cls_count += 1
            if name in self.scope.sub_scopes:
                new_scope = self.scope.sub_scopes[name]
            else:
                non_local = self.get_non_local()
                new_scope = Scope(self.glob_scope, non_local,
                                  self.scope.builtins, self.scope)
            self._enter_scope(name, new_scope, ScopeType.CLASS, cls_temp)
            return cls_temp
        else:
            return None

    def pop_scope(self):
        if len(self.scope_list) <= 1:
            raise ValueError
        scope_type = self.scope_type.pop()
        self.scope_list.pop()
        self.name_list.pop()
        self.scope_temp.pop()
        if scope_type == ScopeType.CLASS:
            self.cls_count -= 1


builtin_scope = Scope(None, None, None, None)  # type: ignore
builtin_scope.glob = builtin_scope
builtin_scope.builtins = builtin_scope
builtin_scope.add_type('float', float_temp)
builtin_scope.add_type('int', int_temp)
builtin_scope.add_type('str', str_temp)
builtin_scope.add_type('bool', bool_temp)
builtin_scope.add_type('Generic', generic_temp)
builtin_scope.add_type('None', none_temp)
builtin_scope.add_type('Any', any_temp)

builtin_scope.add_var('float', float_temp.get_default_type())
builtin_scope.add_var('int', int_temp.get_default_type())
builtin_scope.add_var('str', str_temp.get_default_type())
builtin_scope.add_var('bool', bool_temp.get_default_type())
builtin_scope.add_var('Generic', generic_temp.get_default_type())


def get_init_env(module: TypeModuleTemp):
    """Return the default environment for a module

    Args:
        module: absolute path of the module
    """
    scope = Scope(None, None, None, None)  # type: ignore
    scope.glob = scope
    scope.builtins = builtin_scope

    return Environment(scope, module)
