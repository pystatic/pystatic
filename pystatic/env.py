from collections import OrderedDict
from typing import Dict, Optional
from .typesys import (BaseType, TypeClassTemp, TypeModuleTemp, TypeTemp,
                      TypeIns, any_type, int_type, float_type, bool_type,
                      str_type, generic_type, none_type)
from .fsys import File


def lookup_type_scope(scope: 'Scope', name) -> Optional[TypeTemp]:
    """Look up an type in a Scope"""
    name_list = name.split('.')
    target = scope.types.get(name_list[0])
    i = 1
    while i < len(name_list):
        if isinstance(target, TypeClassTemp):
            target = target.get_type(name_list[i])
        else:
            return None
        if target is None:
            return None
        i += 1
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
        return self._lookup_by_func(Scope.lookup_local_type,
                                    name)  # type: ignore

    def add_type(self, name: str, tp):
        self.types[name] = tp

    def lookup_local_var(self, name: str) -> Optional[TypeIns]:
        return self.local.get(name)

    def lookup_var(self, name: str) -> Optional[TypeIns]:
        return self._lookup_by_func(Scope.lookup_local_var,
                                    name)  # type: ignore

    def add_var(self, name: str, tp: TypeIns):
        self.local[name] = tp


class Environment(object):
    """Environment provides several methods to
    organize type scopes and scopes of a module.
    """
    GLOB_SCOPE = 0
    FUNC_SCOPE = 1
    CLASS_SCOPE = 2

    def __init__(self, scope: Scope, file: File):
        self.scope_list = [scope]
        self.file = file
        self.name_list = [file.module_name]
        self.scope_type = [self.GLOB_SCOPE]

        self.base_index = 0
        self.cls_count = 0

        self.current_cls = None

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
    def absolute_name(self):
        return '.'.join(self.name_list)

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

    def add_type(self, name: str, tp: TypeTemp):
        if self.scope_type[-1] == self.CLASS_SCOPE:
            assert self.scope.parent is not None
            cur_tp = self.scope.parent.lookup_local_type(self.name_list[-1])
            if isinstance(cur_tp, TypeClassTemp):
                cur_tp.add_type(name, tp)
        return self.scope.add_type(name, tp)

    def add_var(self, name: str, tp: TypeIns):
        return self.scope.add_var(name, tp)

    def lookup_local_var(self, name: str):
        return self.scope.lookup_local_var(name)

    def lookup_var(self, name: str) -> Optional[BaseType]:
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

    def _enter_scope(self, name: str, new_scope: 'Scope', scope_type):
        self._try_add_scope(name, new_scope)
        self.scope_list.append(new_scope)
        self.scope_type.append(scope_type)
        self.name_list.append(name)

    def enter_class(self, name: str) -> Optional[TypeClassTemp]:
        """Enter a class scope"""
        res = self.lookup_local_type(name)
        if res:
            assert isinstance(res, TypeClassTemp)
            self.cls_count += 1
            if name in self.scope.sub_scopes:
                new_scope = self.scope.sub_scopes[name]
            else:
                non_local = self.get_non_local()
                new_scope = Scope(self.glob_scope, non_local,
                                  self.scope.builtins, self.scope)
            self._enter_scope(name, new_scope, Environment.CLASS_SCOPE)
            return res
        else:
            return None

    def pop_scope(self):
        if len(self.scope_list) <= 1:
            raise ValueError
        scope_type = self.scope_type.pop()
        self.scope_list.pop()
        self.name_list.pop()
        if scope_type == self.CLASS_SCOPE:
            self.cls_count -= 1

    def to_module(self) -> TypeModuleTemp:
        glob = self.glob_scope
        return TypeModuleTemp(self.file, glob.types, glob.local)


builtin_scope = Scope(None, None, None, None)  # type: ignore
builtin_scope.glob = builtin_scope
builtin_scope.builtins = builtin_scope
builtin_scope.add_type('float', float_type)
builtin_scope.add_type('int', int_type)
builtin_scope.add_type('str', str_type)
builtin_scope.add_type('bool', bool_type)
builtin_scope.add_type('Generic', generic_type)
builtin_scope.add_type('float', float_type)
builtin_scope.add_type('None', none_type)
builtin_scope.add_type('Any', any_type)


def get_init_env(module: File):
    """Return the default environment for a module

    Args:
        module: absolute path of the module
    """
    scope = Scope(None, None, None, None)  # type: ignore
    scope.glob = scope
    scope.builtins = builtin_scope

    return Environment(scope, module)
