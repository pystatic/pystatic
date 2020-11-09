from enum import Enum, auto
from typing import Dict, List, TYPE_CHECKING, Tuple
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

typing_symtable = SymTable('typings', None, None, builtin_symtable,
                           TableScope.GLOB)
typing_symtable.glob = typing_symtable


def get_builtin_symtable() -> SymTable:
    return builtin_symtable


def get_typing_symtable() -> SymTable:
    return typing_symtable


def get_init_module_symtable(symid: SymId) -> SymTable:
    new_symtable = SymTable(symid, None, None, builtin_symtable,
                            TableScope.GLOB)
    new_symtable.glob = new_symtable
    return new_symtable


class TypeVarTemp(TypeClassTemp):
    def __init__(self):
        symtable = typing_symtable.new_symtable('TypeVar', TableScope.CLASS)
        super().__init__('TypeVar', typing_symtable, symtable)

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


class TypeUnionTemp(TypeTemp):
    def __init__(self):
        super().__init__('Union')

    @property
    def module_symid(self) -> str:
        return 'typing'


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

    def get_default_typetype(self) -> 'TypeType':
        return TypePackageType(self)


class TypeListTemp(TypeTemp):
    def __init__(self) -> None:
        super().__init__('List')
        self.placeholders = [_invariant_tpvar]

    @property
    def module_symid(self) -> str:
        return 'typing'

    def get_default_typetype(self) -> 'TypeType':
        return list_type


class TypeTupleTemp(TypeTemp):
    def __init__(self):
        super().__init__('Tuple')

    @property
    def module_symid(self) -> str:
        return 'typing'

    def arity(self) -> int:
        return INFINITE_ARITY

    def get_default_typetype(self) -> 'TypeType':
        return tuple_type


class TypeSetTemp(TypeTemp):
    def __init__(self) -> None:
        super().__init__('Set')
        self.placeholders = [_invariant_tpvar]

    @property
    def module_symid(self) -> str:
        return 'typing'

    def get_default_typetype(self) -> 'TypeType':
        return set_type


class TypeDictTemp(TypeTemp):
    def __init__(self):
        super().__init__('Dict')
        self.placeholders = [_invariant_tpvar, _invariant_tpvar]

    @property
    def module_symid(self) -> str:
        return 'typing'

    def get_default_typetype(self) -> 'TypeType':
        return dict_type


class TypeEllipsisTemp(TypeTemp):
    def __init__(self) -> None:
        super().__init__('ellipsis')

    @property
    def module_symid(self) -> str:
        return 'builtins'

    def get_default_typetype(self) -> 'TypeType':
        return ellipsis_type

    def get_default_ins(self) -> 'TypeIns':
        return ellipsis_ins


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


def add_spt_def(name, temp, ins=None):
    global typing_symtable
    typing_symtable._spt_types[name] = temp
    if ins:
        entry = Entry(ins)
    else:
        entry = Entry(temp.get_default_typetype())
    typing_symtable.add_entry(name, entry)


add_spt_def('Generic', generic_temp)
add_spt_def('Callable', callable_temp)
add_spt_def('Any', any_temp, any_type)
add_spt_def('Tuple', tuple_temp)
add_spt_def('Optional', optional_temp)
add_spt_def('Literal', literal_temp)
add_spt_def('Union', union_temp)
add_spt_def('TypeVar', typevar_temp, typevar_type)
add_spt_def('List', list_temp, list_type)
add_spt_def('Tuple', tuple_temp, tuple_type)
add_spt_def('Dict', dict_temp, dict_type)
add_spt_def('Set', set_temp, set_type)
