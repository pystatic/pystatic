import ast
import copy
from abc import ABC, abstractmethod
from typing import (Any, Optional, List, Final, Dict, TYPE_CHECKING)
from pystatic.option import Option
from pystatic.evalutil import ApplyArgs, GetItemArg
from pystatic.errorcode import NoAttribute

if TYPE_CHECKING:
    from pystatic.predefined import TypeContext, TypeFuncIns, TypeVarIns
    from pystatic.symtable import SymTable
    from pystatic.symid import SymId

BindList = Optional[List[Any]]

DEFAULT_TYPEVAR_NAME: Final[str] = '__unknown_typevar_name__'
INFINITE_ARITY: Final[int] = -1


class TypeIns:
    def __init__(self, temp: 'TypeTemp', bindlist: BindList):
        # bindlist will be shallowly copied
        self.temp = temp
        self.bindlist = copy.copy(bindlist)

    def substitute(self, context: 'TypeContext') -> list:
        context = context or {}
        new_bindlist = []
        bindlist = self.bindlist or []
        for item in bindlist:
            if isinstance(item, TypeVarIns) and item in context:
                # TODO: check consistence here
                new_bindlist.append(context[item])
            else:
                new_bindlist.append(item)
        return new_bindlist

    def shadow(self, context: 'TypeContext') -> 'TypeContext':
        new_context = {**context}
        bindlist = self.bindlist or []
        for i, item in enumerate(bindlist):
            if len(self.temp.placeholders) > i:
                old_slot = self.temp.placeholders[i]
                if isinstance(old_slot,
                              TypeVarIns) and old_slot in new_context:
                    assert isinstance(item, TypeType)
                    new_context[old_slot] = item
        return new_context

    def getattribute(
            self,
            name: str,
            node: Optional[ast.AST],
            context: Optional['TypeContext'] = None) -> Option['TypeIns']:
        context = context or {}
        context = self.shadow(context)

        option_res = Option(any_ins)
        ins_res = self.temp.getattribute(name, self.substitute(context),
                                         context)

        if not ins_res:
            option_res.add_err(NoAttribute(node, self, name))
        else:
            option_res.set_value(ins_res)
        return option_res

    def getattr(self,
                name: str,
                node: Optional[ast.AST],
                context: Optional['TypeContext'] = None) -> Option['TypeIns']:
        return self.getattribute(name, node, context)

    def call(self, applyargs: 'ApplyArgs') -> Option['TypeIns']:
        return self.temp.call(applyargs, self.bindlist)

    def getitem(self, item: GetItemArg) -> Option['TypeIns']:
        # TODO: add error
        return self.temp.getitem(item, self.bindlist)

    def unaryop_mgf(self, op: str, node: ast.UnaryOp) -> Option['TypeIns']:
        return self.temp.unaryop_mgf(self.bindlist, op, node)

    def binop_mgf(self, other: 'TypeIns', op: str,
                  node: ast.BinOp) -> Option['TypeIns']:
        return self.temp.binop_mgf(self.bindlist, other, op, node)

    def equiv(self, other):
        # note that `isinstance(other, TypeIns)` won't reject typeins and typetype
        if other.__class__ != self.__class__:
            return False

        # Every class should have only one template globally
        if self.temp != other.temp:
            return False

        else:
            temp_arity = self.temp.arity()
            # default bind is Any
            if temp_arity == INFINITE_ARITY:
                ext_list1 = copy.copy(self.bindlist) if self.bindlist else []
                ext_list2 = copy.copy(other.bindlist) if other.bindlist else []
                len1 = len(ext_list1)
                len2 = len(ext_list2)
                if len1 < len2:
                    ext_list1.extend([any_ins] * (len2 - len1))
                elif len2 < len1:
                    ext_list2.extend([any_ins] * (len1 - len2))

            else:
                if self.bindlist:
                    diff1 = temp_arity - len(self.bindlist)
                    ext_list1 = self.bindlist + [any_ins] * diff1
                else:
                    ext_list1 = [any_ins] * temp_arity

                if other.bindlist:
                    diff2 = temp_arity - len(other.bindlist)
                    ext_list2 = other.bindlist + [any_ins] * diff2
                else:
                    ext_list2 = [any_ins] * temp_arity

            for i in range(temp_arity):
                if not ext_list1[i].equiv(ext_list2[i]):
                    return False
            return True

    def __str__(self) -> str:
        return self.temp.str_expr(self.bindlist)


class TypeType(TypeIns):
    def __init__(self, temp: 'TypeTemp', bindlist: BindList):
        super().__init__(temp, bindlist)

    def getins(self, typetype_option: Option['TypeIns']) -> 'TypeIns':
        """Get TypeIns from TypeType

        all errors will be stored in typetype_option.
        """
        ins_option = self.temp.getins(self.bindlist)
        typetype_option.combine_error(ins_option)

        return ins_option.value

    def get_default_ins(self) -> 'TypeIns':
        """Get TypeIns from TypeType

        all errors will be stored in typetype_option.
        """
        ins_option = self.temp.getins(self.bindlist)
        return ins_option.value

    def getattribute(
            self,
            name: str,
            node: Optional[ast.AST],
            context: Optional['TypeContext'] = None) -> Option['TypeIns']:
        context = context or {}
        context = self.shadow(context)

        option_res = Option(any_ins)
        ins_res = self.temp.get_type_attribute(name, self.substitute(context),
                                               context)

        if not ins_res:
            err = NoAttribute(node, self, name)
            option_res.add_err(err)
        else:
            option_res.set_value(ins_res)
        return option_res

    def getitem(self, item: GetItemArg) -> Option['TypeIns']:
        return self.temp.get_typetype(self.bindlist, item)

    def call(self, applyargs: 'ApplyArgs') -> Option['TypeIns']:
        return self.temp.init_ins(applyargs, self.bindlist)

    def get_inner_symtable(self):
        return self.temp._inner_symtable

    def __str__(self):
        s = self.temp.str_expr(None)
        return "Type[" + s + ']'


class TypeAlias(TypeType):
    def __init__(self, alias: str, typetype: TypeType):
        super().__init__(typetype.temp, typetype.bindlist)
        self.alias = alias

    def __str__(self):
        return self.alias


class TypeTemp(ABC):
    def __init__(self, name: str):
        self.name = name
        self.placeholders = []

        self._cached_ins = TypeIns(self, None)
        self._cached_typetype = TypeType(self, None)

    @property
    def basename(self) -> str:
        rpos = self.name.rfind('.')
        return self.name[rpos + 1:]

    @property
    @abstractmethod
    def module_symid(self) -> str:
        ...

    def arity(self) -> int:
        return len(self.placeholders)

    # basic
    def getattribute(
            self,
            name: str,
            bindlist: BindList,
            context: Optional['TypeContext'] = None) -> Optional['TypeIns']:
        return None

    def setattr(self, name: str, attr_type: 'TypeIns'):
        assert False, "This function should be avoided because TypeClassTemp doesn't support it"

    def getattr(
            self,
            name: str,
            bindlist: BindList,
            context: Optional['TypeContext'] = None) -> Optional['TypeIns']:
        return self.getattribute(name, bindlist, context)

    def call(self, applyargs: 'ApplyArgs',
             bindlist: BindList) -> Option['TypeIns']:
        call_option = Option(any_ins)
        # TODO: add error for not callable
        # call_option.add_err(...)
        return call_option

    def getitem(self, item: GetItemArg,
                bindlist: BindList) -> Option['TypeIns']:
        option_res = Option(any_ins)
        # TODO: add error
        return option_res

    # magic operation functions(mgf is short for magic function).
    def unaryop_mgf(self, bindlist: BindList, op: str,
                    node: ast.UnaryOp) -> Option['TypeIns']:
        from pystatic.predefined import TypeFuncIns

        option_res = Option(any_ins)
        func = self.getattribute(op, bindlist)
        if not func or not isinstance(func, TypeFuncIns):
            # TODO: add warning here
            return option_res

        else:
            applyargs = ApplyArgs()
            return func.call(applyargs)

    def binop_mgf(self, bindlist: BindList, other: 'TypeIns', op: str,
                  node: ast.BinOp) -> Option['TypeIns']:
        from pystatic.predefined import TypeFuncIns

        option_res = Option(any_ins)
        func = self.getattribute(op, bindlist)
        if not func or not isinstance(func, TypeFuncIns):
            # TODO: add warning here
            return option_res

        else:
            applyargs = ApplyArgs()
            applyargs.add_arg(other, node)
            return func.call(applyargs)

    # some helper methods
    def get_inner_typedef(self, name: str) -> Optional['TypeTemp']:
        return None

    def get_typetype(
            self,
            bindlist: Optional[BindList] = None,
            itemarg: Optional[GetItemArg] = None) -> Option['TypeType']:
        """Mainly used for TypeType to generate correct TypeType"""
        res_option = Option(any_type)
        if not itemarg:
            return Option(TypeType(self, None))
        else:
            if isinstance(itemarg.ins, (tuple, list)):
                tpins_list: List[TypeIns] = []
                for singleitem in itemarg.ins:
                    cur_ins = singleitem.ins
                    if isinstance(cur_ins, TypeType):
                        tpins = cur_ins.getins(res_option)
                        tpins_list.append(tpins)
                    elif isinstance(cur_ins, TypeIns):
                        tpins_list.append(cur_ins)
                    else:
                        # TODO: warning: class Type doesn't support this syntax
                        pass
                res_option.value = TypeType(self, tpins_list)

            else:
                item_ins = itemarg.ins
                if isinstance(item_ins, TypeType):
                    res_option.value = TypeType(self,
                                                [item_ins.getins(res_option)])
                elif isinstance(item_ins, TypeIns):
                    res_option.value = TypeType(self, [item_ins])
                else:
                    # TODO: add warning here
                    res_option.value = TypeType(self, None)

        return res_option

    def get_default_typetype(self) -> 'TypeType':
        return self._cached_typetype

    def getins(self, bindlist: BindList) -> Option['TypeIns']:
        if self.arity == 0 or not bindlist:
            return Option(self._cached_ins)
        else:
            return Option(TypeIns(self, bindlist))

    def get_default_ins(self) -> Option['TypeIns']:
        return Option(self._cached_ins)

    def get_type_attribute(
            self,
            name: str,
            bindlist: BindList,
            context: Optional['TypeContext'] = None) -> Optional['TypeIns']:
        """Get attribute that belong to the Type itself, mainly used for typetype"""
        return self.getattribute(name, bindlist, context)

    def init_ins(self, applyargs: 'ApplyArgs',
                 bindlist: BindList) -> Option['TypeIns']:
        """Initialize an instance

        used when __init__ method should be called.
        """
        # TODO: check consistency
        return self.getins(bindlist)

    # string expression
    def str_expr(self,
                 bindlist: BindList,
                 context: Optional['TypeContext'] = None) -> str:
        """__str__ with bindlist and context"""
        str_bindlist = []
        slot_cnt = self.arity()

        if slot_cnt == INFINITE_ARITY:
            for bind in bindlist:
                str_bindlist.append(f'{bind}')
            return self.name + '[' + ', '.join(str_bindlist) + ']'

        elif slot_cnt == 0:
            return self.name

        if not bindlist:
            str_bindlist = ['Any'] * slot_cnt
        else:
            diff = slot_cnt - len(bindlist)
            assert diff >= 0
            for bind in bindlist:
                str_bindlist.append(f'{bind}')

            str_bindlist.extend(['Any'] * diff)

        assert str_bindlist
        return self.name + '[' + ', '.join(str_bindlist) + ']'

    def __str__(self):
        assert False, "use str_expr instead"


class ModuleNamedTypeTemp(TypeTemp):
    """TypeTemp with module_symid set

    TypeTemp is an abstract class and ModuleNamedTypeTemp makes it convenient
    to create temporary TypeTemp.
    """
    def __init__(self, name: str, module_symid: str) -> None:
        super().__init__(name)
        self._module_symid = module_symid

    @property
    def module_symid(self) -> str:
        return self._module_symid


class TypeClassTemp(TypeTemp):
    def __init__(self, clsname: str, def_symtable: 'SymTable',
                 inner_symtable: 'SymTable'):
        super().__init__(clsname)

        self.baseclass: 'List[TypeIns]'
        self.baseclass = []

        self.var_attr: Dict[str, 'TypeIns'] = {}

        self._inner_symtable = inner_symtable  # symtable belongs to this cls
        self._def_symtable = def_symtable  # symtable where this cls is defined

    @property
    def module_symid(self) -> str:
        return self._def_symtable.glob_symid

    def get_inner_typedef(self, name: str) -> Optional['TypeTemp']:
        cls_def = self._inner_symtable._tp_def
        if name in cls_def:
            return cls_def[name]
        else:
            return None

    def get_inner_symtable(self) -> 'SymTable':
        return self._inner_symtable

    def get_def_symtable(self) -> 'SymTable':
        assert self._def_symtable
        return self._def_symtable

    def get_local_attr(
            self,
            name: str,
            binds: Optional['TypeContext'] = None) -> Optional['TypeIns']:
        if name in self.var_attr:
            return self.var_attr[name]
        else:
            return self._inner_symtable.lookup_local(name)

    def get_type_attribute(
            self, name: str, bindlist: BindList,
            context: Optional['TypeContext']) -> Optional['TypeIns']:
        res = self._inner_symtable.lookup_local(name)
        if not res:
            for basecls in self.baseclass:
                res = basecls.getattribute(name, None, None).value
                if res:
                    break
        return res

    def getattribute(
            self,
            name: str,
            bindlist: BindList,
            context: Optional['TypeContext'] = None) -> Optional['TypeIns']:
        res = self.get_local_attr(name)
        if not res:
            for basecls in self.baseclass:
                res = basecls.getattribute(name, None, None).value
                if res:
                    break
        return res


class TypeAnyTemp(TypeTemp):
    def __init__(self):
        super().__init__('Any')

    @property
    def module_symid(self) -> str:
        return 'typing'

    # basic
    def getattribute(self, name: str, bindlist: BindList,
                     context: Optional['TypeContext']) -> Optional['TypeIns']:
        return self._cached_ins

    def call(self, applyargs: 'ApplyArgs',
             bindlist: BindList) -> Option['TypeIns']:
        return Option(self._cached_ins)

    def getitem(self, item: GetItemArg,
                bindlist: BindList) -> Option['TypeIns']:
        return Option(self._cached_ins)

    # magic operation functions
    def unaryop_mgf(self, bindlist: BindList, op: str,
                    node: ast.UnaryOp) -> Option['TypeIns']:
        return Option(self._cached_ins)

    def binop_mgf(self, bindlist: BindList, other: 'TypeIns', op: str,
                  node: ast.BinOp) -> Option['TypeIns']:
        return Option(self._cached_ins)

    # some helper functions
    def getins(self, bindlist: BindList) -> Option['TypeIns']:
        return Option(self._cached_ins)

    def get_typetype(self, bindlist: Optional[BindList],
                     item: Optional[GetItemArg]) -> Option['TypeType']:
        # TODO: warning: if bindlist is non-empty, then report an error
        return Option(self._cached_typetype)

    def get_default_typetype(self) -> 'TypeType':
        return self._cached_typetype


any_temp = TypeAnyTemp()
any_ins = any_temp.get_default_ins().value
any_type = any_temp.get_default_typetype()
