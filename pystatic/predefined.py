from typing import Final
from pystatic.symtable import TableScope, Entry, SymTable
from pystatic.typesys import *
from pystatic.error.errorcode import *

if TYPE_CHECKING:
    from pystatic.evalutil import GetItemArgs, InsWithAst


TypeVarList = List["TypeVarIns"]

builtins_symtable = SymTable("builtins", None, None, None, None, TableScope.GLOB)
builtins_symtable.glob = builtins_symtable
builtins_symtable.builtins = builtins_symtable

typing_symtable = SymTable(
    "typing", None, None, builtins_symtable, None, TableScope.GLOB
)
typing_symtable.glob = typing_symtable

typing_extensions_symtable = SymTable(
    "typing_extensions", None, None, builtins_symtable, None, TableScope.GLOB
)
typing_extensions_symtable.glob = typing_extensions_symtable

INVARIANT: Final[int] = 1
COVARIANT: Final[int] = 2
CONTRAVARIANT: Final[int] = 3


class TypeNoneTemp(TypeTemp):
    def __init__(self):
        super().__init__("None")

    @property
    def module_symid(self) -> str:
        return "builtins"

    def getattribute(self, name: str, bindlist: BindList) -> Optional["TypeIns"]:
        return None

    def getitem(
        self, item: "GetItemArgs", bindlist: BindList, node: Optional[ast.AST]
    ) -> Result["TypeIns"]:
        # TODO: warning here
        res = Result(self._cached_ins)
        res.add_err(NotSubscriptable(self._cached_ins, node))
        return Result(self._cached_ins)

    def getins(self, bindlist: BindList) -> Result["TypeIns"]:
        return Result(self._cached_ins)

    def getitem_typetype(
        self,
        bindlist: Optional[BindList],
        item: Optional["GetItemArgs"],
        node: Optional[ast.AST] = None,
    ) -> Result["TypeType"]:
        return Result(self._cached_typetype)

    def get_default_ins(self) -> Result["TypeIns"]:
        return Result(self._cached_ins)

    def get_default_typetype(self) -> "TypeType":
        return self._cached_typetype


class TypeUnionTemp(TypeTemp):
    def __init__(self):
        super().__init__("Union")
        self.placeholders = [covariant_tpvar]

    @property
    def module_symid(self) -> str:
        return "typing"

    def arity(self) -> int:
        return INFINITE_ARITY


class TypeOptionalTemp(TypeTemp):
    def __init__(self):
        super().__init__("Optional")
        self.placeholders = [covariant_tpvar]

    @property
    def module_symid(self) -> str:
        return "typing"


class TypeVarTemp(TypeClassTemp):
    def __init__(self):
        symtable = typing_symtable.new_symtable("TypeVar", TableScope.CLASS)
        super().__init__("TypeVar", typing_symtable, symtable)

    def init_ins(self, applyargs: "ApplyArgs", bindlist: BindList) -> Result[TypeIns]:
        def extract_value(ins_ast: Optional["InsWithAst"], expect_type):
            if not ins_ast:
                return None

            if isinstance(ins_ast.value, TypeLiteralIns):
                value = ins_ast.value.value
                if isinstance(value, expect_type):
                    return value
                else:
                    # TODO: add error here
                    return None
            else:
                # TODO: add error here
                return None

        default_ins = TypeVarIns(DEFAULT_TYPEVAR_NAME, bound=any_ins)
        ins_result = Result(default_ins)
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
                if rangenode.value == none_ins:
                    default_ins.constraints.append(rangenode.value)
                else:
                    assert isinstance(rangenode.value, TypeType), "expect typetype"
                    rangeins = rangenode.value.getins(ins_result)
                    default_ins.constraints.append(rangeins)

        cova = applyargs.kwargs.get("covariant")
        contra = applyargs.kwargs.get("contravariant")
        if not cova:
            covariant = False
        else:
            covariant = extract_value(cova, bool)
        if not contra:
            contravariant = False
        else:
            contravariant = extract_value(contra, bool)

        bound_ins_ast = applyargs.kwargs.get("bound")
        if bound_ins_ast:
            if default_ins.constraints:
                raise NotImplementedError()
            bound = bound_ins_ast.value
            # TODO: re-implement this, make it more accurate
            if isinstance(bound, TypeType):
                default_ins.bound = bound.get_default_ins()
            else:
                default_ins.bound = bound

        if covariant and contravariant:
            raise NotImplementedError()

        # TODO: warning if both covariant and contravariant is True
        if covariant:
            default_ins.kind = COVARIANT
        elif contravariant:
            default_ins.kind = CONTRAVARIANT
        else:
            default_ins.kind = INVARIANT

        return ins_result


class TypeVarIns(TypeIns):
    def __init__(
        self,
        tpvar_name: str,
        *args: "TypeIns",
        bound: Optional["TypeIns"] = None,
        kind=INVARIANT,
    ):
        super().__init__(typevar_temp, None)
        self.tpvar_name = tpvar_name
        self.bound = bound
        assert kind == INVARIANT or kind == COVARIANT or kind == CONTRAVARIANT
        self.kind = kind
        self.constraints: List["TypeIns"] = list(*args)


class TypeCallableTemp(TypeTemp):
    def __init__(self):
        super().__init__("Callable")

    @property
    def module_symid(self) -> str:
        return "typing"

    def arity(self) -> int:
        return 2

    def getitem_typetype(
        self, bindlist: BindList, itemarg: "GetItemArgs", node: Optional[ast.AST] = None
    ) -> Result["TypeType"]:
        res_bindlist = []
        res = TypeType(self, [ellipsis_ins, any_ins])
        result = Result(res)

        if not self._getitem_typetype_check_bindlist(bindlist, result, node):
            result.value = TypeType(self, bindlist)
            return result

        items = itemarg.items
        callable_err = "Parameter list doesn't match Callable's structure"

        if len(items) != 2:
            result.add_err(IndiceGeneralError(callable_err, node))
            return result
        else:
            arg_part = items[0]
            ret_part = items[1]

            if arg_part.value == ellipsis_ins:
                res_bindlist.append(ellipsis_ins)
            else:
                if not isinstance(arg_part.value, (list, tuple)):
                    result.add_err(IndiceGeneralError(callable_err, node))
                    return result
                arglist = []
                for argitem in arg_part.value:
                    self._getitem_typetype_accept_item(argitem, result, arglist)
                res_bindlist.append(arglist)
            self._getitem_typetype_accept_item(ret_part, result, res_bindlist)
            res.bindlist = res_bindlist
            return result


class TypeGenericTemp(TypeTemp):
    def __init__(self):
        super().__init__("Generic")

    @property
    def module_symid(self) -> str:
        return "typing"

    def getitem_typetype(
        self, bindlist: BindList, itemarg: "GetItemArgs", node: Optional[ast.AST]
    ) -> Result["TypeType"]:
        res_bindlist = []
        res = TypeType(self, res_bindlist)
        result = Result(res)

        if not self._getitem_typetype_check_bindlist(bindlist, result, node):
            result.value = TypeType(self, bindlist)
            return result

        items = itemarg.items
        for item in items:
            value = item.value
            node = item.node
            if not isinstance(value, TypeVarIns):
                result.add_err(IndiceGeneralError("Expect a TypeVar", node))
            else:
                res_bindlist.append(value)
        return result


class TypeProtocolTemp(TypeTemp):
    def __init__(self) -> None:
        super().__init__("Protocol")

    def arity(self) -> int:
        return INFINITE_ARITY

    @property
    def module_symid(self) -> str:
        return "typing"


class TypeTypeAnnTemp(TypeTemp):
    def __init__(self):
        super().__init__("Type")

    @property
    def module_symid(self) -> str:
        return "typing"

    def arity(self) -> int:
        return 1

    def getins(self, bindlist: BindList) -> Result["TypeIns"]:
        if not bindlist or len(bindlist) != 1:
            # FIXME: add error here
            return Result(any_ins)

        if not isinstance(bindlist[0], TypeIns):
            raise NotImplementedError()

        if isinstance(bindlist[0], TypeType):
            return Result(bindlist[0])
        else:
            return Result(TypeType(bindlist[0].temp, None))


class TypeListTemp(TypeClassTemp):
    def __init__(self) -> None:
        symtable = typing_symtable.new_symtable("List", TableScope.CLASS)
        super().__init__("List", typing_symtable, symtable)
        self.placeholders = [invariant_tpvar]


class TypeTupleTemp(TypeClassTemp):
    def __init__(self):
        symtable = typing_symtable.new_symtable("Tuple", TableScope.CLASS)
        super().__init__("Tuple", typing_symtable, symtable)
        self.placeholders = [covariant_tpvar]

    @property
    def module_symid(self) -> str:
        return "typing"

    def arity(self) -> int:
        return INFINITE_ARITY

    def getitem_typetype(
        self, bindlist: BindList, itemarg: "GetItemArgs", node: Optional[ast.AST]
    ) -> Result["TypeType"]:
        result = super().getitem_typetype(bindlist, itemarg, node)
        try:
            if result.value.bindlist[0] == ellipsis_ins:
                result.add_err(
                    IndiceGeneralError(
                        "'...' allowed only as the second of two arguments", node
                    )
                )
            return result
        except IndexError:
            return result

    def get_default_ins(self) -> Result["TypeIns"]:
        return Result(self._cached_ins)

    def get_default_typetype(self) -> "TypeType":
        return self._cached_typetype


class TypeSetTemp(TypeClassTemp):
    def __init__(self) -> None:
        symtable = typing_symtable.new_symtable("Set", TableScope.CLASS)
        super().__init__("Set", typing_symtable, symtable)
        self.placeholders = [invariant_tpvar]

    @property
    def module_symid(self) -> str:
        return "typing"

    def get_default_typetype(self) -> "TypeType":
        return self._cached_typetype


class TypeDictTemp(TypeClassTemp):
    def __init__(self):
        symtable = typing_symtable.new_symtable("Dict", TableScope.CLASS)
        super().__init__("Dict", typing_symtable, symtable)
        self.placeholders = [invariant_tpvar, invariant_tpvar]

    @property
    def module_symid(self) -> str:
        return "typing"

    def get_default_typetype(self) -> "TypeType":
        return self._cached_typetype


class TypeEllipsisTemp(TypeClassTemp):
    def __init__(self) -> None:
        symtable = builtins_symtable.new_symtable("ellipsis", TableScope.CLASS)
        super().__init__("ellipsis", builtins_symtable, symtable)

    @property
    def module_symid(self) -> str:
        return "builtins"

    def get_default_typetype(self) -> "TypeType":
        return self._cached_typetype

    def get_default_ins(self) -> Result["TypeIns"]:
        return Result(self._cached_ins)

    def str_expr(self, bindlist: BindList) -> str:
        return "..."


class TypeLiteralTemp(TypeTemp):
    def __init__(self) -> None:
        super().__init__("Literal")

    @property
    def module_symid(self) -> str:
        return "typing"

    def arity(self) -> int:
        return 1

    def getitem_typetype(
        self, bindlist: BindList, itemarg: "GetItemArgs", node: Optional[ast.AST] = None
    ) -> Result["TypeType"]:
        result = Result(any_ins)

        if not self._getitem_typetype_check_bindlist(bindlist, result, node):
            result.value = TypeType(self, bindlist)
            return result

        items = itemarg.items
        if len(items) != 1:
            # TODO: many false positive
            result.add_err(IndiceParamNumberMismatch(len(items), 1, node))
        constant = items[0].value
        constant_node = items[0].node

        if isinstance(constant, TypeLiteralIns):
            result.value = TypeType(self, constant.bindlist)
        elif isinstance(constant, (list, tuple, TypeIns)):
            result.add_err(
                IndiceGeneralError(
                    "Literal's indice should be literal value", constant_node
                )
            )
            result.value = any_ins
        else:
            res = TypeType(self, [constant])
            result.value = res
        return result

    def getins(self, bindlist: BindList) -> Result["TypeIns"]:
        if bindlist:
            return Result(TypeLiteralIns(bindlist[0]))
        else:
            return Result(any_ins)


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
        fmt = "Literal[{}]"
        if isinstance(value, str):
            return fmt.format(f"'{value}'")
        else:
            return fmt.format(str(value))


class TypeModuleIns(TypeIns):
    def __init__(self, symtable: "SymTable", consultant=None) -> None:
        super().__init__(module_temp, None)
        self._inner_symtable = symtable
        self.consultant = consultant

    @property
    def symid(self):
        return self._inner_symtable.symid

    def set_consultant(self, consultant):
        assert hasattr(consultant, "getattribute")
        self.consultant = consultant

    def clear_consultant(self):
        self.consultant = None

    def get_inner_symtable(self):
        return self._inner_symtable

    def getattribute(self, name: str, node: Optional[ast.AST]) -> Result["TypeIns"]:
        res = self._inner_symtable.legb_lookup(name)
        if res:
            return Result(res)
        elif self.consultant:
            return self.consultant.getattribute(name, node)
        else:
            result = Result(any_ins)
            result.add_err(SymbolUndefined(node, name))
            return result


class TypePackageIns(TypeModuleIns):
    def __init__(self, symtable: "SymTable", paths: List[str], consultant=None) -> None:
        super().__init__(symtable, consultant)
        self.paths = paths
        self.submodule = {}

    def add_submodule(self, name: str, module_ins: TypeModuleIns):
        # FIXME: modify this
        self.submodule[name] = module_ins
        self._inner_symtable.add_entry(name, Entry(module_ins))


# add pre-defined types to special symtables
def _add_cls_to_symtable(name: str, def_sym: "SymTable"):
    symtable = def_sym.new_symtable(name, TableScope.CLASS)
    clstemp = TypeClassTemp(name, builtins_symtable, symtable)
    clstype = clstemp.get_default_typetype()
    clsins = clstemp.get_default_ins().value

    def_sym.add_entry(name, Entry(clstype))
    def_sym.add_type_def(name, clstemp)

    return clstemp, clstype, clsins


def _add_spt_to_symtable(
    spt_temp_cls: Type[TypeTemp], def_sym: "SymTable", *args, **kwargs
):
    """Add special types to typing"""
    spt_temp = spt_temp_cls(*args, **kwargs)
    def_sym.add_type_def(spt_temp.name, spt_temp)
    spt_type = spt_temp.get_default_typetype()
    def_sym.add_entry(spt_temp.name, Entry(spt_type))
    return spt_temp, spt_type, spt_temp.get_default_ins().value


def _add_temp_to_symtable(
    name: str, temp: "TypeTemp", typetype: "TypeType", symtable: "SymTable"
):
    symtable.add_type_def(name, temp)
    symtable.add_entry(name, Entry(typetype))


# typing.py:
typing_symtable.add_type_def("Any", any_temp)
typing_symtable.add_entry("Any", Entry(any_type))


typevar_temp, typevar_type, _ = _add_spt_to_symtable(TypeVarTemp, typing_symtable)

invariant_tpvar = TypeVarIns("invariant_tpvar", bound=any_ins, kind=INVARIANT)
covariant_tpvar = TypeVarIns("covariant_tpvar", bound=any_ins, kind=COVARIANT)
contravariant_tpvar = TypeVarIns(
    "contravariant_tpvar", bound=any_ins, kind=CONTRAVARIANT
)

list_temp, list_type, _ = _add_spt_to_symtable(TypeListTemp, typing_symtable)
tuple_temp, tuple_type, _ = _add_spt_to_symtable(TypeTupleTemp, typing_symtable)
dict_temp, dict_type, _ = _add_spt_to_symtable(TypeDictTemp, typing_symtable)
set_temp, set_type, _ = _add_spt_to_symtable(TypeSetTemp, typing_symtable)
optional_temp, optional_type, _ = _add_spt_to_symtable(
    TypeOptionalTemp, typing_symtable
)
literal_temp, literal_type, _ = _add_spt_to_symtable(TypeLiteralTemp, typing_symtable)
generic_temp, generic_type, _ = _add_spt_to_symtable(TypeGenericTemp, typing_symtable)
protocol_temp, protocol_type, _ = _add_spt_to_symtable(
    TypeProtocolTemp, typing_symtable
)
union_temp, union_type, _ = _add_spt_to_symtable(TypeUnionTemp, typing_symtable)
callable_temp, callable_type, _ = _add_spt_to_symtable(
    TypeCallableTemp, typing_symtable
)
Type_temp, Type_type, _ = _add_spt_to_symtable(TypeTypeAnnTemp, typing_symtable)

# builtins.py
object_temp, object_type, object_ins = _add_cls_to_symtable("object", builtins_symtable)
int_temp, int_type, int_ins = _add_cls_to_symtable("int", builtins_symtable)
float_temp, float_type, float_ins = _add_cls_to_symtable("float", builtins_symtable)
str_temp, str_type, str_ins = _add_cls_to_symtable("str", builtins_symtable)
bool_temp, bool_type, bool_ins = _add_cls_to_symtable("bool", builtins_symtable)
complex_temp, complex_type, complex_ins = _add_cls_to_symtable(
    "complex", builtins_symtable
)
byte_temp, byte_type, byte_ins = _add_cls_to_symtable("byte", builtins_symtable)
slice_temp, slice_type, slice_ins = _add_cls_to_symtable("slice", builtins_symtable)
none_temp, none_type, none_ins = _add_spt_to_symtable(TypeNoneTemp, builtins_symtable)
ellipsis_temp, ellipsis_type, ellipsis_ins = _add_spt_to_symtable(
    TypeEllipsisTemp, builtins_symtable
)

type_meta_temp = TypeClassTemp(
    "type",
    builtins_symtable,
    builtins_symtable.new_symtable("type", TableScope.CLASS),
    None,
)
type_meta_ins = type_meta_temp.get_default_ins().value
type_meta_type = type_meta_temp.get_default_typetype()
_add_temp_to_symtable("type", type_meta_temp, type_meta_type, builtins_symtable)
_add_temp_to_symtable("list", list_temp, list_type, builtins_symtable)
_add_temp_to_symtable("dict", dict_temp, dict_type, builtins_symtable)
_add_temp_to_symtable("set", set_temp, set_type, builtins_symtable)

# typing_extension.py
typing_extensions_symtable.add_type_def("Literal", literal_temp)
typing_extensions_symtable.add_entry("Literal", Entry(literal_type))
