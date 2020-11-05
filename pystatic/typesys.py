import ast
import copy
from enum import Enum, auto, IntEnum
from typing import (Any, Optional, Dict, List, Tuple, Union, TYPE_CHECKING,
                    Final)
from pystatic.option import Option
from pystatic.symid import SymId
from pystatic.evalutil import (InsWithAst, ApplyArgs, GetItemType, WithAst)
from pystatic.symtable import Entry, SymTable
from pystatic.errorcode import NoAttribute

if TYPE_CHECKING:
    from pystatic.arg import Argument

TypeContext = Dict['TypeVarIns', 'TypeIns']
TypeVarList = List['TypeVarIns']
BindList = Optional[List[Any]]

DEFAULT_TYPEVAR_NAME: Final[str] = '__unknown_typevar_name__'
INFINITE_ARITY: Final[int] = -1


class TpVarKind(Enum):
    INVARIANT = auto()
    COVARIANT = auto()
    CONTRAVARIANT = auto()


class TpState(IntEnum):
    FRESH = 1
    ON = 2
    OVER = 3


class TypeTemp:
    def __init__(self,
                 name: str,
                 module_symid: str,
                 resolve_state: TpState = TpState.OVER):
        self.name = name
        self.placeholders = []

        self.module_symid = module_symid  # the module symid that define this type
        self._resolve_state = resolve_state

    @property
    def basename(self) -> str:
        rpos = self.name.rfind('.')
        return self.name[rpos + 1:]

    def arity(self) -> int:
        return len(self.placeholders)

    # basic
    def getattribute(
            self,
            name: str,
            bindlist: BindList,
            context: Optional[TypeContext] = None) -> Optional['TypeIns']:
        return None

    def setattr(self, name: str, attr_type: 'TypeIns'):
        assert False, "This function should be avoided because TypeClassTemp doesn't support it"

    def getattr(self,
                name: str,
                bindlist: BindList,
                context: Optional[TypeContext] = None) -> Optional['TypeIns']:
        return self.getattribute(name, bindlist, context)

    def call(self, applyargs: 'ApplyArgs',
             bindlist: BindList) -> Option['TypeIns']:
        call_option = Option(any_ins)
        # TODO: add error for not callable
        # call_option.add_err(...)
        return call_option

    def getitem(self, item: GetItemType,
                bindlist: BindList) -> Option['TypeIns']:
        option_res = Option(any_ins)
        # TODO: add error
        return option_res

    # magic operation functions(mgf is short for magic function).
    def unaryop_mgf(self, bindlist: BindList, op: str,
                    node: ast.UnaryOp) -> Option['TypeIns']:
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

    def get_typetype(self,
                     bindlist: Optional[BindList] = None,
                     item: Optional[GetItemType] = None) -> Option['TypeType']:
        """Mainly used for TypeType to generate correct TypeType"""
        res_option = Option(any_type)
        if not item:
            return Option(TypeType(self, None))
        else:
            if isinstance(item.ins, (tuple, list)):
                tpins_list: List[TypeIns] = []
                for singleitem in item.ins:
                    cur_ins = singleitem.ins
                    if isinstance(cur_ins, TypeType):
                        tpins = cur_ins.getins(res_option)  # type: ignore
                        tpins_list.append(tpins)
                    elif isinstance(cur_ins, TypeIns):
                        tpins_list.append(cur_ins)
                    else:
                        # TODO: add warning here
                        pass
                res_option.value = TypeType(self, tpins_list)

            else:
                if isinstance(item.ins, TypeIns):
                    res_option.value = TypeType(self, [item.ins])
                else:
                    # TODO: add warning here
                    res_option.value = TypeType(self, None)

        return res_option

    def get_default_typetype(self) -> 'TypeType':
        return self.get_typetype(None, None).value

    def getins(self, bindlist: BindList) -> Option['TypeIns']:
        return Option(TypeIns(self, bindlist))

    def get_default_ins(self) -> Option['TypeIns']:
        return self.getins(None)

    def get_type_attribute(
            self,
            name: str,
            bindlist: BindList,
            context: Optional[TypeContext] = None) -> Optional['TypeIns']:
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
                 context: Optional[TypeContext] = None) -> str:
        """__str__ with bindlist and context"""
        str_bindlist = []
        slot_cnt = self.arity()

        if slot_cnt == INFINITE_ARITY:
            for bind in bindlist:
                str_bindlist.append(f'{bind}')
            return self.name + '[' + ','.join(str_bindlist) + ']'

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


class TypeIns:
    def __init__(self, temp: TypeTemp, bindlist: BindList):
        """bindlist will be shallowly copied"""
        self.temp = temp
        self.bindlist = copy.copy(bindlist)

    def substitute(self, context: TypeContext) -> list:
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

    def shadow(self, context: TypeContext) -> TypeContext:
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
            context: Optional[TypeContext] = None) -> Option['TypeIns']:
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
                context: Optional[TypeContext] = None) -> Option['TypeIns']:
        return self.getattribute(name, node, context)

    def call(self, applyargs: 'ApplyArgs') -> Option['TypeIns']:
        return self.temp.call(applyargs, self.bindlist)

    def getitem(self, item: GetItemType) -> Option['TypeIns']:
        # TODO: add error
        return self.temp.getitem(item, self.bindlist)

    def unaryop_mgf(self, op: str, node: ast.UnaryOp) -> Option['TypeIns']:
        return self.temp.unaryop_mgf(self.bindlist, op, node)

    def binop_mgf(self, other: 'TypeIns', op: str,
                  node: ast.BinOp) -> Option['TypeIns']:
        return self.temp.binop_mgf(self.bindlist, other, op, node)

    def __eq__(self, other):
        # note that `isinstance(other, TypeIns)` won't reject typeins and typetype
        if other.__class__ != self.__class__:
            return False

        # Every class should have only one template globally
        if self.temp != other.temp:
            return False

        else:
            temp_arity = self.temp.arity()
            # default bind is Any
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
                if ext_list1[i] != ext_list2[i]:
                    return False
            return True

    def __hash__(self):
        return hash(id(self))

    def __ne__(self, other):
        return not (self == other)

    def __str__(self) -> str:
        return self.temp.str_expr(self.bindlist)


class TypeType(TypeIns):
    def __init__(self, temp: TypeTemp, bindlist: BindList):
        super().__init__(temp, bindlist)

    def getins(self, typetype_option: Option['TypeIns']) -> 'TypeIns':
        """Get TypeIns from TypeType

        all errors will be stored in typetype_option.
        """
        ins_option = self.temp.getins(self.bindlist)
        typetype_option.combine_error(ins_option)

        return ins_option.value

    def getattribute(
            self,
            name: str,
            node: Optional[ast.AST],
            context: Optional[TypeContext] = None) -> Option['TypeIns']:
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

    def getitem(self, item: GetItemType) -> Option['TypeIns']:
        return self.temp.get_typetype(self.bindlist, item)

    def call(self, applyargs: 'ApplyArgs') -> Option['TypeIns']:
        return self.temp.init_ins(applyargs, self.bindlist)

    def get_inner_symtable(self):
        return self.temp._inner_symtable

    def __str__(self):
        s = self.temp.str_expr(None)
        return "Type[" + s + ']'


class TypeVarTemp(TypeTemp):
    def __init__(self):
        super().__init__('TypeVar', 'typing')

    def init_ins(self, applyargs: 'ApplyArgs',
                 bindlist: BindList) -> Option[TypeIns]:
        def extract_value(ins_ast: Optional[InsWithAst], expect_type):
            if not ins_ast:
                return None

            if isinstance(ins_ast.ins, TypeLiteralIns):
                value = ins_ast.ins.value
                if isinstance(value, expect_type):
                    return value
                else:
                    # TODO: add error here
                    return None
            else:
                # TODO: add error here
                return None

        default_ins = TypeVarIns(DEFAULT_TYPEVAR_NAME, bound=any_ins)
        ins_option = Option(default_ins)
        args_rear = 0

        if applyargs.args:
            name = extract_value(applyargs.args[0], str)
            if name:
                default_ins.tpvar_name = name
            else:
                assert False, "TODO"
            args_rear = 1
        else:
            assert False, "TODO"

        if len(applyargs.args) > args_rear:
            default_ins.bound = None
            for rangenode in applyargs.args[args_rear:]:
                assert isinstance(rangenode.ins, TypeType), "expect typetype"
                rangeins = rangenode.ins.getins(ins_option)
                default_ins.constrains.append(rangeins)

        cova = applyargs.kwargs.get('covariant')
        if not cova:
            covariant = False
        else:
            covariant = extract_value(cova, bool)
            if not covariant:
                assert False, "TODO"

        contra = applyargs.kwargs.get('contravariant')
        if not contra:
            contravariant = False
        else:
            contravariant = extract_value(contra, bool)
            if not contravariant:
                assert False, "TODO"

        bound_ins_ast = applyargs.kwargs.get('bound')
        if bound_ins_ast:
            if default_ins.constrains:
                assert False, "TODO"
            bound = bound_ins_ast.ins
            assert isinstance(bound, TypeType), "TODO"
            default_ins.bound = bound

        if covariant and contravariant:
            assert False, "TODO"

        if covariant:
            default_ins.kind = TpVarKind.COVARIANT
        elif contravariant:
            default_ins.kind = TpVarKind.CONTRAVARIANT
        else:
            default_ins.kind = TpVarKind.INVARIANT

        return ins_option


class TypeVarIns(TypeIns):
    def __init__(self,
                 tpvar_name: str,
                 *args: 'TypeIns',
                 bound: Optional['TypeIns'] = None,
                 kind: TpVarKind = TpVarKind.INVARIANT):
        super().__init__(typevar_temp, None)
        self.tpvar_name = tpvar_name
        self.bound = bound
        assert kind == TpVarKind.INVARIANT or kind == TpVarKind.COVARIANT or kind == TpVarKind.CONTRAVARIANT
        self.kind = kind
        self.constrains: List['TypeIns'] = list(*args)


class TypeClassTemp(TypeTemp):
    # FIXME: remove None of symtable and defnode
    def __init__(self,
                 clsname: str,
                 module_symid: str,
                 state: TpState,
                 def_symtable: 'SymTable',
                 inner_symtable: 'SymTable',
                 defnode: ast.ClassDef = None):
        super().__init__(clsname, module_symid, state)

        self.baseclass: 'List[TypeType]'
        self.baseclass = []

        self.var_attr: Dict[str, 'TypeIns'] = {}

        self._inner_symtable = inner_symtable  # symtable belongs to this cls
        self._def_symtable = def_symtable  # symtable where this cls is defined
        self._defnode = defnode

        self._glob_symid = module_symid  # the module symid that this class is defined

    def get_inner_typedef(self, name: str) -> Optional['TypeTemp']:
        cls_defs = self._inner_symtable._cls_defs
        spt_defs = self._inner_symtable._spt_types
        if name in cls_defs:
            return cls_defs[name]
        elif name in spt_defs:
            return spt_defs[name]
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
            binds: Optional[TypeContext] = None) -> Optional['TypeIns']:
        if name in self.var_attr:
            return self.var_attr[name]
        else:
            return self._inner_symtable.lookup_local(name)

    def get_type_attribute(
            self, name: str, bindlist: BindList,
            context: Optional[TypeContext]) -> Optional['TypeIns']:
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
            context: Optional[TypeContext] = None) -> Optional['TypeIns']:
        res = self.get_local_attr(name)
        if not res:
            for basecls in self.baseclass:
                res = basecls.getattribute(name, None, None).value
                if res:
                    break
        return res


class TypeFuncTemp(TypeTemp):
    def __init__(self):
        super().__init__('function', 'builtins', TpState.OVER)


class TypeModuleTemp(TypeClassTemp):
    def __init__(self, symid: SymId, symtable: 'SymTable'):
        # FIXME: inner_symtable and def_symtable should be different
        super().__init__(symid, symid, TpState.OVER, symtable, symtable)

    @property
    def symid(self):
        return self.name

    def get_inner_typedef(self, name: str) -> Optional['TypeTemp']:
        return self._inner_symtable.get_type_def(name)


class TypePackageTemp(TypeModuleTemp):
    def __init__(self, paths: List[str], symtable: 'SymTable', symid: SymId):
        super().__init__(symid, symtable)
        self.paths = paths

    def get_default_typetype(self) -> 'TypeType':
        return TypePackageType(self)


class TypeAnyTemp(TypeTemp):
    def __init__(self):
        super().__init__('Any', 'typing')

    # basic
    def getattribute(self, name: str, bindlist: BindList,
                     context: Optional[TypeContext]) -> Optional['TypeIns']:
        return any_ins

    def call(self, applyargs: 'ApplyArgs',
             bindlist: BindList) -> Option['TypeIns']:
        return Option(any_ins)

    def getitem(self, item: GetItemType,
                bindlist: BindList) -> Option['TypeIns']:
        return Option(any_ins)

    # magic operation functions
    def unaryop_mgf(self, bindlist: BindList, op: str,
                    node: ast.UnaryOp) -> Option['TypeIns']:
        return Option(any_ins)

    def binop_mgf(self, bindlist: BindList, other: 'TypeIns', op: str,
                  node: ast.BinOp) -> Option['TypeIns']:
        return Option(any_ins)

    # some helper functions
    def getins(self, bindlist: BindList) -> Option['TypeIns']:
        return Option(any_ins)

    def get_typetype(self, bindlist: Optional[BindList],
                     item: Optional[GetItemType]) -> Option['TypeType']:
        return Option(any_type)

    def get_default_typetype(self) -> 'TypeType':
        return any_type


class TypeNoneTemp(TypeTemp):
    def __init__(self):
        super().__init__('None', 'typing')

    def getattribute(self, name: str, bindlist: BindList,
                     context: Optional[TypeContext]) -> Optional['TypeIns']:
        return None

    def call(self, applyargs: 'ApplyArgs',
             bindlist: BindList) -> Option['TypeIns']:
        # TODO: warning
        return Option(none_ins)

    def getitem(self, item: GetItemType,
                bindlist: BindList) -> Option['TypeIns']:
        # TODO: warning
        return Option(none_ins)

    def unaryop_mgf(self, bindlist: BindList, op: str,
                    node: ast.UnaryOp) -> Option['TypeIns']:
        res_option = Option(none_ins)
        res_option.add_err(NoAttribute(node, none_ins, 'None'))
        return res_option

    def binop_mgf(self, bindlist: BindList, other: 'TypeIns', op: str,
                  node: ast.BinOp) -> Option['TypeIns']:
        res_option = Option(none_ins)
        res_option.add_err(NoAttribute(node, none_ins, 'None'))
        return res_option

    def getins(self, bindlist: BindList) -> Option['TypeIns']:
        return Option(none_ins)

    def get_typetype(self, bindlist: Optional[BindList],
                     item: Optional[GetItemType]) -> Option['TypeType']:
        return Option(none_type)

    def get_default_typetype(self) -> 'TypeType':
        return none_type


class TypeListTemp(TypeTemp):
    def __init__(self) -> None:
        super().__init__('List', 'typing')
        self.placeholders = [_invariant_tpvar]

    def get_default_typetype(self) -> 'TypeType':
        return list_type


class TypeTupleTemp(TypeTemp):
    def __init__(self):
        super().__init__('Tuple', 'typing')

    def arity(self) -> int:
        return INFINITE_ARITY

    def get_default_typetype(self) -> 'TypeType':
        return tuple_type


class TypeSetTemp(TypeTemp):
    def __init__(self) -> None:
        super().__init__('Set', 'typing')
        self.placeholders = [_invariant_tpvar]

    def get_default_typetype(self) -> 'TypeType':
        return set_type


class TypeDictTemp(TypeTemp):
    def __init__(self):
        super().__init__('Dict', 'typing')
        self.placeholders = [_invariant_tpvar, _invariant_tpvar]

    def get_default_typetype(self) -> 'TypeType':
        return dict_type


class TypeUnionTemp(TypeTemp):
    def __init__(self):
        super().__init__('Union', 'typing')


class TypeOptionalTemp(TypeTemp):
    def __init__(self):
        super().__init__('Optional', 'typing')
        self.placeholders = [_covariant_tpvar]


class TypeEllipsisTemp(TypeTemp):
    def __init__(self) -> None:
        super().__init__('ellipsis', 'typing')

    def get_default_typetype(self) -> 'TypeType':
        return ellipsis_type

    def get_default_ins(self) -> 'TypeIns':
        return ellipsis_ins


class TypeCallableTemp(TypeTemp):
    def __init__(self):
        super().__init__('Callable', 'typing')


class TypeGenericTemp(TypeTemp):
    def __init__(self):
        super().__init__('Generic', 'typing')

    def getitem(self, item: GetItemType,
                bindlist: BindList) -> Option['TypeIns']:
        res = TypeIns(generic_temp, None)
        option_res = Option(res)
        if isinstance(item.ins, (tuple, list)):
            for subitem in item.ins:
                if isinstance(subitem.ins, TypeVarIns):
                    if not res.bindlist:
                        assert isinstance(subitem.ins, TypeVarIns)
                        res.bindlist = [subitem.ins]  # type: ignore
                    else:
                        res.bindlist.append(subitem.ins)
                else:
                    # TODO: add error here
                    pass
        else:
            assert isinstance(item.ins, TypeIns)
            if isinstance(item.ins, TypeVarIns):
                res.bindlist = [item.ins]
            else:
                # option_res.add_err()  # TODO: add error here
                pass
        return option_res


class TypeLiteralTemp(TypeTemp):
    def __init__(self) -> None:
        super().__init__('Literal', 'typing')

    def arity(self) -> int:
        return 1


class TypeLiteralIns(TypeIns):
    def __init__(self, value):
        super().__init__(literal_temp, [value])

    @property
    def value(self):
        assert self.bindlist
        return self.bindlist[0]

    def __str__(self):
        assert self.bindlist
        assert len(self.bindlist) == 1
        value = self.value
        fmt = 'Literal[{}]'
        if isinstance(value, str):
            return fmt.format(f"'{value}'")
        else:
            return fmt.format(str(value))


class TypePackageType(TypeType):
    def __init__(self, temp: TypePackageTemp) -> None:
        super().__init__(temp, None)

    def getins(self, typetype_option: Option['TypeIns']) -> 'TypeIns':
        assert isinstance(self.temp, TypePackageTemp)
        return TypePackageIns(self.temp)


class TypePackageIns(TypeIns):
    def __init__(self, pkgtemp: TypePackageTemp) -> None:
        super().__init__(pkgtemp, None)
        self.submodule: Dict[str, TypeIns] = {}  # submodule

    def add_submodule(self, name: str, ins: TypeIns):
        self.submodule[name] = ins
        assert isinstance(self.temp, TypePackageTemp)
        inner_sym = self.temp.get_inner_symtable()
        inner_sym.add_entry(name, Entry(ins))


class OverloadItem:
    __slots__ = ['argument', 'ret_type']

    def __init__(self, argument: 'Argument', ret_type: 'TypeIns') -> None:
        self.argument = argument
        self.ret_type = ret_type


class TypeFuncIns(TypeIns):
    def __init__(self, funname: str, module_symid: str,
                 inner_symtable: 'SymTable', argument: 'Argument',
                 ret: TypeIns) -> None:
        super().__init__(func_temp, None)
        self.overloads: List[OverloadItem] = [OverloadItem(argument, ret)]
        self.funname = funname
        self.module_symid = module_symid

        self._inner_symtable = inner_symtable

    def add_overload(self, argument: 'Argument', ret: TypeIns):
        self.overloads.append(OverloadItem(argument, ret))

    def get_inner_symtable(self) -> 'SymTable':
        return self._inner_symtable

    def str_expr(self,
                 bindlist: BindList,
                 context: Optional[TypeContext] = None) -> str:
        if len(self.overloads) == 1:
            fun_fmt = "{}{} -> {}"
        else:
            fun_fmt = "@overload {}{} -> {}"
        lst = [
            fun_fmt.format(self.funname, item.argument, item.ret_type)
            for item in self.overloads
        ]
        return '\n'.join(lst)

    def get_func_def(self) -> Tuple['Argument', 'TypeIns']:
        return self.overloads[0].argument, self.overloads[0].ret_type

    def call(self, applyargs: 'ApplyArgs') -> Option['TypeIns']:
        # TODO: deal with arguments
        assert self.overloads
        return Option(self.overloads[0].ret_type)


any_temp = TypeAnyTemp()
any_ins = TypeIns(any_temp, None)
any_type = TypeType(any_temp, None)

ellipsis_temp = TypeEllipsisTemp()
ellipsis_ins = TypeIns(ellipsis_temp, None)
ellipsis_type = TypeType(ellipsis_temp, None)

none_temp = TypeNoneTemp()
none_ins = TypeIns(none_temp, None)
none_type = TypeType(none_temp, None)

typevar_temp = TypeVarTemp()
typevar_type = TypeType(typevar_temp, None)
func_temp = TypeFuncTemp()

_invariant_tpvar = TypeVarIns('_invariant_tpvar',
                              bound=any_ins,
                              kind=TpVarKind.INVARIANT)
_covariant_tpvar = TypeVarIns('_covariant_tpvar',
                              bound=any_ins,
                              kind=TpVarKind.COVARIANT)
_contravariant_tpvar = TypeVarIns('_contravariant_tpvar',
                                  bound=any_ins,
                                  kind=TpVarKind.CONTRAVARIANT)

list_temp = TypeListTemp()
list_type = TypeType(list_temp, None)

tuple_temp = TypeTupleTemp()
tuple_type = TypeType(tuple_temp, None)

dict_temp = TypeDictTemp()
dict_type = TypeType(dict_temp, None)

set_temp = TypeSetTemp()
set_type = TypeType(set_temp, None)

optional_temp = TypeOptionalTemp()
union_temp = TypeUnionTemp()
callable_temp = TypeCallableTemp()
generic_temp = TypeGenericTemp()
literal_temp = TypeLiteralTemp()
