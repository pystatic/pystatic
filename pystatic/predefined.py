from enum import Enum, auto
from typing import Dict, List, TYPE_CHECKING, Tuple, Type
from pystatic.symtable import SymTable, TableScope, Entry
from pystatic.arg import Argument
from pystatic.symid import SymId
from pystatic.typesys import *

if TYPE_CHECKING:
    from pystatic.evalutil import InsWithAst


class TpVarKind(Enum):
    INVARIANT = auto()
    COVARIANT = auto()
    CONTRAVARIANT = auto()


TypeContext = Dict['TypeVarIns', 'TypeIns']
TypeVarList = List['TypeVarIns']

builtin_symtable = SymTable('builtins', None, None, None, TableScope.GLOB)
builtin_symtable.glob = builtin_symtable
builtin_symtable.builtins = builtin_symtable

typing_symtable = SymTable('typing', None, None, builtin_symtable,
                           TableScope.GLOB)
typing_symtable.glob = typing_symtable

typing_symtable.add_type_def('Any', any_temp)
typing_symtable.add_entry('Any', Entry(any_type))


def get_builtin_symtable() -> SymTable:
    return builtin_symtable


def get_typing_symtable() -> SymTable:
    return typing_symtable


def get_init_module_symtable(symid: SymId) -> SymTable:
    new_symtable = SymTable(symid, None, None, builtin_symtable,
                            TableScope.GLOB)
    new_symtable.glob = new_symtable
    return new_symtable


def _add_cls_to_symtable(name: str, def_sym: 'SymTable'):
    symtable = def_sym.new_symtable(name, TableScope.CLASS)
    clstemp = TypeClassTemp(name, builtin_symtable, symtable)
    clstype = clstemp.get_default_typetype()
    clsins = clstemp.get_default_ins().value

    def_sym.add_entry(name, Entry(clstype))
    def_sym.add_type_def(name, clstemp)

    return clstemp, clstype, clsins


def _add_spt_to_symtable(spt_temp_cls: Type[TypeTemp], def_sym: 'SymTable',
                         *args, **kwargs):
    """Add special types to typing"""
    spt_temp = spt_temp_cls(*args, **kwargs)
    def_sym.add_type_def(spt_temp.name, spt_temp)
    spt_type = spt_temp.get_default_typetype()
    def_sym.add_entry(spt_temp.name, Entry(spt_type))
    return spt_temp, spt_type, spt_temp.get_default_ins().value


int_temp, int_type, int_ins = _add_cls_to_symtable('int', builtin_symtable)
float_temp, float_type, float_ins = _add_cls_to_symtable(
    'float', builtin_symtable)
str_temp, str_type, str_ins = _add_cls_to_symtable('str', builtin_symtable)
bool_temp, bool_type, bool_ins = _add_cls_to_symtable('bool', builtin_symtable)
complex_temp, complex_type, complex_ins = _add_cls_to_symtable(
    'complex', builtin_symtable)
byte_temp, byte_type, byte_ins = _add_cls_to_symtable('byte', builtin_symtable)


class TypeVarTemp(TypeClassTemp):
    def __init__(self):
        symtable = typing_symtable.new_symtable('TypeVar', TableScope.CLASS)
        super().__init__('TypeVar', typing_symtable, symtable)

    def init_ins(self, applyargs: 'ApplyArgs',
                 bindlist: BindList) -> Option[TypeIns]:
        def extract_value(ins_ast: Optional['InsWithAst'], expect_type):
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
                default_ins.constraints.append(rangeins)

        cova = applyargs.kwargs.get('covariant')
        contra = applyargs.kwargs.get('contravariant')
        if not cova:
            covariant = False
        else:
            covariant = extract_value(cova, bool)
        if not contra:
            contravariant = False
        else:
            contravariant = extract_value(contra, bool)

        bound_ins_ast = applyargs.kwargs.get('bound')
        if bound_ins_ast:
            if default_ins.constraints:
                raise NotImplementedError()
            bound = bound_ins_ast.ins
            assert isinstance(bound, TypeType), "TODO"
            default_ins.bound = bound.get_default_ins()

        if covariant and contravariant:
            raise NotImplementedError()

        # TODO: warning if both covariant and contravariant is True
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
        self.constraints: List['TypeIns'] = list(*args)


class TypeTypeAnnTemp(TypeTemp):
    def __init__(self):
        super().__init__('Type')

    @property
    def module_symid(self) -> str:
        return 'typing'

    def arity(self) -> int:
        return 1

    def getins(self, bindlist: BindList) -> Option['TypeIns']:
        if not bindlist or len(bindlist) != 1:
            raise NotImplementedError()  # TODO: warning here

        if not isinstance(bindlist[0], TypeIns):
            raise NotImplementedError()

        if isinstance(bindlist[0], TypeType):
            return Option(bindlist[0])
        else:
            return Option(TypeType(bindlist[0].temp, None))


class TypeUnionTemp(TypeTemp):
    def __init__(self):
        super().__init__('Union')

    @property
    def module_symid(self) -> str:
        return 'typing'

    def arity(self) -> int:
        return INFINITE_ARITY


class TypeOptionalTemp(TypeTemp):
    def __init__(self):
        super().__init__('Optional')
        self.placeholders = [_covariant_tpvar]

    @property
    def module_symid(self) -> str:
        return 'typing'


class TypeNoneTemp(TypeTemp):
    def __init__(self):
        super().__init__('None')

    @property
    def module_symid(self) -> str:
        return 'builtins'

    def getattribute(self, name: str, bindlist: BindList,
                     context: Optional[TypeContext]) -> Optional['TypeIns']:
        return None

    def call(self, applyargs: 'ApplyArgs',
             bindlist: BindList) -> Option['TypeIns']:
        # TODO: warning
        return Option(self._cached_ins)

    def getitem(self, item: GetItemArg,
                bindlist: BindList) -> Option['TypeIns']:
        # TODO: warning
        return Option(self._cached_ins)

    def unaryop_mgf(self, bindlist: BindList, op: str,
                    node: ast.UnaryOp) -> Option['TypeIns']:
        none_ins = self._cached_ins
        res_option = Option(none_ins)
        res_option.add_error(NoAttribute(node, none_ins, 'None'))
        return res_option

    def binop_mgf(self, bindlist: BindList, other: 'TypeIns', op: str,
                  node: ast.BinOp) -> Option['TypeIns']:
        none_ins = self._cached_ins
        res_option = Option(none_ins)
        res_option.add_error(NoAttribute(node, none_ins, 'None'))
        return res_option

    def getins(self, bindlist: BindList) -> Option['TypeIns']:
        return Option(self._cached_ins)

    def getitem_typetype(self, bindlist: Optional[BindList],
                         item: Optional[GetItemArg]) -> Option['TypeType']:
        return Option(self._cached_typetype)

    def get_default_ins(self) -> Option['TypeIns']:
        return Option(self._cached_ins)

    def get_default_typetype(self) -> 'TypeType':
        return self._cached_typetype


class TypeFuncTemp(TypeTemp):
    def __init__(self):
        super().__init__('function')

    @property
    def module_symid(self) -> str:
        return 'builtins'


class TypeModuleTemp(TypeClassTemp):
    def __init__(self, symid: SymId, symtable: 'SymTable'):
        # FIXME: inner_symtable and def_symtable should be different
        super().__init__(symid, symtable, symtable)

    @property
    def symid(self):
        return self.name

    def get_inner_typedef(self, name: str) -> Optional['TypeTemp']:
        return self._inner_symtable.get_type_def(name)


class TypePackageTemp(TypeModuleTemp):
    def __init__(self, paths: List[str], symtable: 'SymTable', symid: SymId):
        super().__init__(symid, symtable)
        self.paths = paths
        self._cached_typetype = TypePackageType(self)

    def get_default_typetype(self) -> 'TypeType':
        return self._cached_typetype


class TypeListTemp(TypeClassTemp):
    def __init__(self) -> None:
        symtable = typing_symtable.new_symtable('List', TableScope.CLASS)
        super().__init__('List', typing_symtable, symtable)
        self.placeholders = [_invariant_tpvar]


class TypeTupleTemp(TypeClassTemp):
    def __init__(self):
        symtable = typing_symtable.new_symtable('Tuple', TableScope.CLASS)
        super().__init__('Tuple', typing_symtable, symtable)
        self.placeholders = [_covariant_tpvar]

    @property
    def module_symid(self) -> str:
        return 'typing'

    def arity(self) -> int:
        return INFINITE_ARITY

    def get_default_ins(self) -> Option['TypeIns']:
        return Option(self._cached_ins)

    def get_default_typetype(self) -> 'TypeType':
        return self._cached_typetype


class TypeSetTemp(TypeClassTemp):
    def __init__(self) -> None:
        symtable = typing_symtable.new_symtable('Set', TableScope.CLASS)
        super().__init__('Set', typing_symtable, symtable)
        self.placeholders = [_invariant_tpvar]

    @property
    def module_symid(self) -> str:
        return 'typing'

    def get_default_typetype(self) -> 'TypeType':
        return self._cached_typetype


class TypeDictTemp(TypeClassTemp):
    def __init__(self):
        symtable = typing_symtable.new_symtable('Dict', TableScope.CLASS)
        super().__init__('Dict', typing_symtable, symtable)
        self.placeholders = [_invariant_tpvar, _invariant_tpvar]

    @property
    def module_symid(self) -> str:
        return 'typing'

    def get_default_typetype(self) -> 'TypeType':
        return self._cached_typetype


class TypeEllipsisTemp(TypeTemp):
    def __init__(self) -> None:
        super().__init__('ellipsis')

    @property
    def module_symid(self) -> str:
        return 'builtins'

    def get_default_typetype(self) -> 'TypeType':
        return self._cached_typetype

    def get_default_ins(self) -> Option['TypeIns']:
        return Option(self._cached_ins)

    def str_expr(self,
                 bindlist: BindList,
                 context: Optional['TypeContext'] = None) -> str:
        return '...'


class TypeCallableTemp(TypeTemp):
    def __init__(self):
        super().__init__('Callable')

    @property
    def module_symid(self) -> str:
        return 'typing'


class TypeGenericTemp(TypeTemp):
    def __init__(self):
        super().__init__('Generic')

    @property
    def module_symid(self) -> str:
        return 'typing'

    def getitem(self, item: GetItemArg,
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


class TypeProtocolTemp(TypeTemp):
    def __init__(self) -> None:
        super().__init__('Protocol')

    @property
    def module_symid(self) -> str:
        return 'typing'


class TypeLiteralTemp(TypeTemp):
    def __init__(self) -> None:
        super().__init__('Literal')

    @property
    def module_symid(self) -> str:
        return 'typing'

    def arity(self) -> int:
        return 1


class TypeLiteralIns(TypeIns):
    def __init__(self, value):
        super().__init__(literal_temp, [value])

    @property
    def value(self):
        assert self.bindlist
        return self.bindlist[0]

    def get_value_type(self) -> TypeIns:
        value = self.value
        if isinstance(value, bool):
            return bool_ins
        if isinstance(value, int):
            return int_ins
        elif isinstance(value, float):
            return float_ins
        elif isinstance(value, bytes):
            return byte_ins
        elif isinstance(value, complex):
            return complex_ins
        elif isinstance(value, str):
            return str_ins
        else:
            raise TypeError(value)
            return any_ins

    def equiv(self, other):
        if other.__class__ != self.__class__:
            return False

        s_bindlist = self.bindlist or []
        o_bindlist = other.bindlist or []
        listlen = len(s_bindlist)
        if listlen != len(o_bindlist):
            return False

        for i in range(listlen):
            if s_bindlist[i] != o_bindlist[i]:
                return False

        return True

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

    def get_func_name(self):
        return self.funname

    def call(self, applyargs: 'ApplyArgs') -> Option['TypeIns']:
        # TODO: deal with arguments
        assert self.overloads
        return Option(self.overloads[0].ret_type)


typevar_temp, typevar_type, _ = _add_spt_to_symtable(TypeVarTemp,
                                                     typing_symtable)
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

list_temp, list_type, _ = _add_spt_to_symtable(TypeListTemp, typing_symtable)
tuple_temp, tuple_type, _ = _add_spt_to_symtable(TypeTupleTemp,
                                                 typing_symtable)
dict_temp, dict_type, _ = _add_spt_to_symtable(TypeDictTemp, typing_symtable)
set_temp, set_type, _ = _add_spt_to_symtable(TypeSetTemp, typing_symtable)
optional_temp, optional_type, _ = _add_spt_to_symtable(TypeOptionalTemp,
                                                       typing_symtable)
literal_temp, literal_type, _ = _add_spt_to_symtable(TypeLiteralTemp,
                                                     typing_symtable)
generic_temp, generic_type, _ = _add_spt_to_symtable(TypeGenericTemp,
                                                     typing_symtable)
protocol_temp, protocol_type, _ = _add_spt_to_symtable(TypeProtocolTemp,
                                                       typing_symtable)
union_temp, union_type, _ = _add_spt_to_symtable(TypeUnionTemp,
                                                 typing_symtable)
callable_temp, callable_type, _ = _add_spt_to_symtable(TypeCallableTemp,
                                                       typing_symtable)
Type_temp, Type_type, _ = _add_spt_to_symtable(TypeTypeAnnTemp,
                                               typing_symtable)

none_temp, none_type, none_ins = _add_spt_to_symtable(TypeNoneTemp,
                                                      builtin_symtable)
ellipsis_temp, ellipsis_type, ellipsis_ins = _add_spt_to_symtable(
    TypeEllipsisTemp, builtin_symtable)

type_meta_temp = TypeClassTemp(
    'type', builtin_symtable,
    builtin_symtable.new_symtable('type', TableScope.CLASS), None)
type_meta_ins = type_meta_temp.get_default_ins().value
builtin_symtable.add_type_def('type', type_meta_temp)
builtin_symtable.add_entry('type', Entry(type_meta_ins))
