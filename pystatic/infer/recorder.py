import ast
from typing import List, Dict, Set, Union
from pystatic.error.errorcode import SymbolUndefined
from pystatic.typesys import TypeIns, TypeType, any_type
from pystatic.predefined import (
    TypeFuncIns,
    TypeModuleIns,
    TypeUnionTemp,
    TypeLiteralIns,
    builtins_symtable,
    none_ins,
)
from pystatic.result import Result
from pystatic.symtable import SymTable
from pystatic.TypeCompatible.simpleType import type_consistent

ScopeType = Union[TypeType, TypeFuncIns, TypeModuleIns]


class StoredType:
    def __init__(self, pre_type: TypeIns, is_permanent: bool):
        self.pre_type = pre_type
        self.is_permanent = is_permanent


class Scope:
    def __init__(self, tp: ScopeType):
        self.type_map: Dict[str, TypeIns] = {}
        self.tp = tp

    def set_type(self, name: str, tp: TypeIns):
        self.type_map[name] = tp


class FuncScope(Scope):
    def __init__(
        self, tp: TypeFuncIns, args: Dict[str, TypeIns], ret_annotation: TypeIns
    ):
        super().__init__(tp)
        self.type_map = args
        self.ret_annotation = ret_annotation
        self.ret_types: Set[TypeIns] = set()


class ClassScope(Scope):
    def __init__(self, tp: TypeType):
        super().__init__(tp)


class ModuleScope(Scope):
    def __init__(self, tp: TypeModuleIns):
        super().__init__(tp)


class SymbolRecorder:
    """record the appeared symbol"""

    def __init__(self, module):
        self.stack: List[Scope] = []
        self.stack.append(ModuleScope(module))

    @property
    def cur_scope(self) -> Scope:
        return self.stack[-1]

    def is_defined(self, name: str):
        return name in self.cur_scope.type_map

    def enter_scope(self, tp: ScopeType):
        self.stack.append(Scope(tp))

    def leave_scope(self):
        self.stack.pop()

    def enter_func(self, tp: TypeFuncIns, args: Dict[str, TypeIns], ret_annotation):
        self.stack.append(FuncScope(tp, args, ret_annotation))

    def leave_func(self):
        self.leave_scope()

    def enter_cls(self, tp: TypeType):
        self.stack.append(ClassScope(tp))

    def leave_cls(self):
        self.leave_scope()

    def add_ret(self, ret_type: TypeIns):
        cur_scope = self.cur_scope
        assert isinstance(cur_scope, FuncScope)
        cur_scope.ret_types.add(ret_type)

    def get_ret_annotation(self):
        cur_scope = self.cur_scope
        assert isinstance(cur_scope, FuncScope)
        return cur_scope.ret_annotation

    def get_ret_type(self):
        cur_scope = self.cur_scope
        assert isinstance(cur_scope, FuncScope)
        ret = cur_scope.ret_types
        return ret

    def clear_ret_val(self):
        self.cur_scope.ret_types = set()

    def reset_ret_val(self):
        cur_scope = self.cur_scope
        assert isinstance(cur_scope, FuncScope)
        ret_list = list(self.get_ret_type())
        num = len(ret_list)
        if num == 0:
            cur_scope.tp.overloads[0].ret_type = none_ins
        elif num == 1:
            cur_scope.tp.overloads[0].ret_type = ret_list[0]
        else:
            union_type = make_union_type(ret_list)
            cur_scope.tp.overloads[0].ret_type = union_type

    def record_type(self, name: str, tp: TypeIns):
        self.cur_scope.set_type(name, tp)

    def get_comment_type(self, name) -> TypeIns:
        scope = self.cur_scope
        table: SymTable = scope.tp.get_inner_symtable()
        tp = table.legb_lookup(name)
        if tp:
            return tp
        assert False, f"undefined {name}"

    def get_run_time_type(self, name: str):
        tp = self.cur_scope.type_map.get(name)
        if tp:
            return tp
        table = self.stack[-1].tp.get_inner_symtable()
        tp = table.egb_lookup(name)
        return tp

    def getattribute(self, name: str, node: ast.AST) -> Result:
        tp = self.get_run_time_type(name)
        if tp:
            return Result(tp)
        else:
            option: Result = Result(any_type)
            option.add_err(SymbolUndefined(node, name))
            return option

    def recover_type(self, dirty_map: Dict[str, StoredType]):
        for name, stored_type in dirty_map.items():
            if not stored_type.is_permanent:
                self.record_type(name, stored_type.pre_type)
            else:
                pre_type = stored_type.pre_type
                cur_type = self.get_run_time_type(name)
                if type_consistent(pre_type, cur_type):
                    self.record_type(name, cur_type)
                else:
                    union_type = make_union_type([pre_type, cur_type])
                    self.record_type(name, union_type)


def literal_to_normal_type(literal_ins: TypeLiteralIns):
    val = literal_ins.value
    name = type(val).__name__
    builtin_type = builtins_symtable.legb_lookup(name)
    assert builtin_type
    return builtin_type.call(None).value


def make_union_type(type_list) -> TypeIns:
    bindlist: List[TypeIns] = []
    for tp in type_list:
        if tp.temp.name == "Union":
            bindlist.extend(tp.bindlist)
        elif isinstance(tp, TypeLiteralIns):
            bindlist.append(literal_to_normal_type(tp))
        else:
            bindlist.append(tp)
    bindlist = list(set(bindlist))
    tmp = TypeUnionTemp()
    return TypeIns(tmp, bindlist)
