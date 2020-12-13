import ast
import copy
from abc import ABC, abstractmethod
from typing import Any, Optional, List, Final, Dict, TYPE_CHECKING
from pystatic.option import Option
from pystatic.errorcode import *

if TYPE_CHECKING:
    from pystatic.symtable import SymTable
    from pystatic.evalutil import ApplyArgs, GetItemArgs, WithAst
    from pystatic.arg import Argument

BindList = Optional[List[Any]]

DEFAULT_TYPEVAR_NAME: Final[str] = "__unknown_typevar_name__"
INFINITE_ARITY: Final[int] = -1


class TypeIns:
    def __init__(self, temp: "TypeTemp", bindlist: BindList):
        # bindlist will be shallowly copied
        self.temp = temp
        self.bindlist = bindlist

    def getattribute(self, name: str, node: Optional[ast.AST]) -> Option["TypeIns"]:
        option_res = Option(any_ins)
        ins_res = self.temp.getattribute(name, self.bindlist)

        if not ins_res:
            option_res.add_err(NoAttribute(node, self, name))
        else:
            option_res.set_value(ins_res)
        return option_res

    def getattr(self, name: str, node: Optional[ast.AST]) -> Option["TypeIns"]:
        return self.getattribute(name, node)

    def call(
        self, applyargs: "ApplyArgs", node: Optional[ast.Call]
    ) -> Option["TypeIns"]:
        return self.temp.call(applyargs, self, node)

    def getitem(
        self, item: "GetItemArgs", node: Optional[ast.AST] = None
    ) -> Option["TypeIns"]:
        # TODO: add error
        return self.temp.getitem(item, self.bindlist, node)

    def unaryop_mgf(self, op: str, node: ast.UnaryOp) -> Option["TypeIns"]:
        return self.temp.unaryop_mgf(self.bindlist, op, node)

    def binop_mgf(
        self, other: "TypeIns", op: str, node: ast.BinOp
    ) -> Option["TypeIns"]:
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
    def __init__(self, temp: "TypeTemp", bindlist: BindList):
        super().__init__(temp, bindlist)

    def getins(self, typetype_option: Option["TypeIns"]) -> "TypeIns":
        """Get TypeIns from TypeType

        all errors will be stored in typetype_option.
        """
        ins_option = self.temp.getins(self.bindlist)
        typetype_option.combine_error(ins_option)

        return ins_option.value

    def get_default_ins(self) -> "TypeIns":
        """Get TypeIns from TypeType

        all errors will be stored in typetype_option.
        """
        ins_option = self.temp.getins(self.bindlist)
        return ins_option.value

    def getattribute(self, name: str, node: Optional[ast.AST]) -> Option["TypeIns"]:
        option_res = Option(any_ins)
        ins_res = self.temp.get_type_attribute(name, self.bindlist)

        if not ins_res:
            err = NoAttribute(node, self, name)
            option_res.add_err(err)
        else:
            option_res.set_value(ins_res)
        return option_res

    def getitem(
        self, item: "GetItemArgs", node: Optional[ast.AST] = None
    ) -> Option["TypeIns"]:
        return self.temp.getitem_typetype(self.bindlist, item, node)

    def call(
        self, applyargs: "ApplyArgs", node: Optional[ast.Call]
    ) -> Option["TypeIns"]:
        return self.temp.init_ins(applyargs, self.bindlist)

    def get_inner_symtable(self):
        assert isinstance(self.temp, TypeClassTemp)
        return self.temp._inner_symtable

    def __str__(self):
        s = self.temp.str_expr(None)
        return "Type[" + s + "]"


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
        rpos = self.name.rfind(".")
        return self.name[rpos + 1 :]

    @property
    @abstractmethod
    def module_symid(self) -> str:
        ...

    def arity(self) -> int:
        return len(self.placeholders)

    # basic
    def getattribute(self, name: str, bindlist: BindList) -> Optional["TypeIns"]:
        return None

    def getattr(self, name: str, bindlist: BindList) -> Optional["TypeIns"]:
        return self.getattribute(name, bindlist)

    def call(
        self, applyargs: "ApplyArgs", typeins: "TypeIns", node: Optional[ast.Call]
    ) -> Option["TypeIns"]:
        res_option = Option(any_ins)
        call_func = self.getattribute("__call__", typeins.bindlist)
        if not call_func or call_func.temp != func_temp:
            res_option.add_err(NotCallable(typeins, node))
        else:
            res_option = call_func.call(applyargs, node)
        return res_option

    def getitem(
        self, item: "GetItemArgs", bindlist: BindList, node: Optional[ast.AST]
    ) -> Option["TypeIns"]:
        option_res = Option(any_ins)
        # TODO: add error
        return option_res

    # magic operation functions(mgf is short for magic function).
    def unaryop_mgf(
        self, bindlist: BindList, op: str, node: ast.UnaryOp
    ) -> Option["TypeIns"]:
        from pystatic.evalutil import ApplyArgs

        option_res = Option(any_ins)
        func = self.getattribute(op, bindlist)
        if not func or not isinstance(func, TypeFuncIns):
            # TODO: add warning here
            return option_res

        else:
            applyargs = ApplyArgs()
            return func.call(applyargs, node)

    def binop_mgf(
        self, bindlist: BindList, other: "TypeIns", op: str, node: ast.BinOp
    ) -> Option["TypeIns"]:
        from pystatic.evalutil import ApplyArgs

        option_res = Option(any_ins)
        func = self.getattribute(op, bindlist)
        if not func or not isinstance(func, TypeFuncIns):
            node.op
            # TODO: add warning here
            return option_res

        else:
            applyargs = ApplyArgs()
            applyargs.add_arg(other, node)
            return func.call(applyargs, node)

    # some helper methods
    def get_inner_typedef(self, name: str) -> Optional["TypeTemp"]:
        return None

    def _getitem_typetype_check_bindlist(
        self, bindlist, res_option: Option, node
    ) -> bool:
        if bindlist is not None:
            res_option.add_err(NotSubscriptable(TypeIns(self, bindlist), node))
            return False
        return True

    def _getitem_typetype_check_arity(
        self, itemarg: "GetItemArgs", res_option: Option, node
    ) -> bool:
        items = itemarg.items
        len_items = len(items)
        assert len_items > 0
        arity = self.arity()
        if arity == INFINITE_ARITY:
            return True
        elif arity != len_items:
            res_option.add_err(IndiceParamNumberMismatch(len_items, arity, node))
            return False
        else:
            return True

    def _getitem_typetype_accept_item(
        self, item: "WithAst", res_option: Option, res_bindlist: BindList
    ):
        value = item.value
        node = item.node
        if not isinstance(value, TypeIns):
            res_option.add_err(IndiceParamNotClass(node))
        elif not isinstance(value, TypeType):
            from pystatic.predefined import (
                ellipsis_ins,
                none_ins,
                TypeVarIns,
                TypeAlias,
            )

            if not (
                value == ellipsis_ins
                or value == none_ins
                or isinstance(value, (TypeVarIns, TypeAlias))
            ):
                res_option.add_err(IndiceParamNotClass(node))
            res_bindlist.append(value)
        else:
            res_bindlist.append(value.get_default_ins())

    def getitem_typetype(
        self, bindlist: BindList, itemarg: "GetItemArgs", node: Optional[ast.AST] = None
    ) -> Option["TypeType"]:
        """Mainly used for TypeType to generate correct TypeType"""
        res_bindlist = []
        res_option = Option(TypeType(self, res_bindlist))

        if not self._getitem_typetype_check_bindlist(bindlist, res_option, node):
            res_option.value = TypeType(self, bindlist)
            return res_option
        self._getitem_typetype_check_arity(itemarg, res_option, node)

        if self.arity() == INFINITE_ARITY:
            len_items = len(itemarg.items)
        else:
            len_items = min(self.arity(), len(itemarg.items))
        pad_cnt = max(self.arity() - len_items, 0)
        for i in range(len_items):
            self._getitem_typetype_accept_item(
                itemarg.items[i], res_option, res_bindlist
            )
        res_bindlist.extend([any_ins] * pad_cnt)
        return res_option

    def get_default_typetype(self) -> "TypeType":
        return self._cached_typetype

    def getins(self, bindlist: BindList) -> Option["TypeIns"]:
        if self.arity == 0 or not bindlist:
            return Option(self._cached_ins)
        else:
            return Option(TypeIns(self, bindlist))

    def get_default_ins(self) -> Option["TypeIns"]:
        return Option(self._cached_ins)

    def get_type_attribute(self, name: str, bindlist: BindList) -> Optional["TypeIns"]:
        """Get attribute that belong to the Type itself, mainly used for TypeType"""
        return self.getattribute(name, bindlist)

    def init_ins(self, applyargs: "ApplyArgs", bindlist: BindList) -> Option["TypeIns"]:
        """Initialize an instance

        used when __init__ method should be called.
        """
        # TODO: check consistency
        return self.getins(bindlist)

    # string expression
    def str_expr(self, bindlist: BindList) -> str:
        """__str__ with bindlist and context"""
        str_bindlist = []
        slot_cnt = self.arity()

        if slot_cnt == INFINITE_ARITY:
            if not bindlist:
                return self.name

            for bind in bindlist:
                str_bindlist.append(f"{bind}")
            return self.name + "[" + ", ".join(str_bindlist) + "]"

        elif slot_cnt == 0:
            return self.name

        if not bindlist:
            str_bindlist = ["Any"] * slot_cnt
        else:
            diff = slot_cnt - len(bindlist)
            assert diff >= 0
            for bind in bindlist:
                str_bindlist.append(f"{bind}")

            str_bindlist.extend(["Any"] * diff)

        assert str_bindlist
        return self.name + "[" + ", ".join(str_bindlist) + "]"

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
    def __init__(
        self,
        clsname: str,
        def_symtable: "SymTable",
        inner_symtable: "SymTable",
        metaclass: Optional[TypeIns] = None,
    ):
        super().__init__(clsname)

        self.baseclass: "List[TypeIns]"
        self.baseclass = []

        self.metaclass = metaclass

        self.var_attr: Dict[str, "TypeIns"] = {}

        self._inner_symtable = inner_symtable  # symtable belongs to this cls
        self._def_symtable = def_symtable  # symtable where this cls is defined

    @property
    def module_symid(self) -> str:
        return self._def_symtable.glob_symid

    def get_inner_typedef(self, name: str) -> Optional["TypeTemp"]:
        cls_def = self._inner_symtable._tp_def
        if name in cls_def:
            return cls_def[name]
        else:
            return None

    def get_inner_symtable(self) -> "SymTable":
        return self._inner_symtable

    def get_def_symtable(self) -> "SymTable":
        assert self._def_symtable
        return self._def_symtable

    def get_local_attr(self, name: str) -> Optional["TypeIns"]:
        if name in self.var_attr:
            return self.var_attr[name]
        else:
            return self._inner_symtable.lookup_local(name)

    def get_type_attribute(self, name: str, bindlist: BindList) -> Optional["TypeIns"]:
        res = self._inner_symtable.lookup_local(name)
        if not res:
            for basecls in self.baseclass:
                res = basecls.getattribute(name, None).value
                if res:
                    break
        return res

    def getattribute(self, name: str, bindlist: BindList) -> Optional["TypeIns"]:
        res = self.get_local_attr(name)
        if not res:
            for basecls in self.baseclass:
                res = basecls.getattribute(name, None).value
                if res:
                    break
        return res


class TypeAnyTemp(TypeTemp):
    def __init__(self):
        super().__init__("Any")

    @property
    def module_symid(self) -> str:
        return "typing"

    # basic
    def getattribute(self, name: str, bindlist: BindList) -> Optional["TypeIns"]:
        return self._cached_ins

    def call(
        self, applyargs: "ApplyArgs", typeins: "TypeIns", node: Optional[ast.Call]
    ) -> Option["TypeIns"]:
        return Option(self._cached_ins)

    def getitem(
        self, item: "GetItemArgs", bindlist: BindList, node: Optional[ast.AST] = None
    ) -> Option["TypeIns"]:
        return Option(self._cached_ins)

    # magic operation functions
    def unaryop_mgf(
        self, bindlist: BindList, op: str, node: ast.UnaryOp
    ) -> Option["TypeIns"]:
        return Option(self._cached_ins)

    def binop_mgf(
        self, bindlist: BindList, other: "TypeIns", op: str, node: ast.BinOp
    ) -> Option["TypeIns"]:
        return Option(self._cached_ins)

    # some helper functions
    def getins(self, bindlist: BindList) -> Option["TypeIns"]:
        return Option(self._cached_ins)

    def getitem_typetype(
        self, bindlist: BindList, item: "GetItemArgs", node: Optional[ast.AST] = None
    ) -> Option["TypeType"]:
        # TODO: warning: if bindlist is non-empty, then report an error
        return Option(self._cached_typetype)

    def get_default_typetype(self) -> "TypeType":
        return self._cached_typetype


class TypeFuncTemp(TypeTemp):
    def __init__(self):
        super().__init__("function")

    @property
    def module_symid(self) -> str:
        return "builtins"


class TypeModuleTemp(TypeTemp):
    def __init__(self) -> None:
        super().__init__("module")

    @property
    def module_symid(self) -> str:
        return "builtins"


class OverloadItem:
    __slots__ = ["argument", "ret_type"]

    def __init__(self, argument: "Argument", ret_type: "TypeIns") -> None:
        self.argument = argument
        self.ret_type = ret_type


class TypeFuncIns(TypeIns):
    def __init__(
        self,
        funname: str,
        module_symid: str,
        inner_symtable: "SymTable",
        argument: "Argument",
        ret: TypeIns,
    ) -> None:
        super().__init__(func_temp, None)
        self.overloads: List[OverloadItem] = [OverloadItem(argument, ret)]
        self.funname = funname
        self.module_symid = module_symid

        self._inner_symtable = inner_symtable

    def add_overload(self, argument: "Argument", ret: TypeIns):
        self.overloads.append(OverloadItem(argument, ret))

    def get_inner_symtable(self) -> "SymTable":
        return self._inner_symtable

    def str_expr(self, bindlist: BindList) -> str:
        if len(self.overloads) == 1:
            fun_fmt = "{}{} -> {}"
        else:
            fun_fmt = "@overload {}{} -> {}"
        lst = [
            fun_fmt.format(self.funname, item.argument, item.ret_type)
            for item in self.overloads
        ]
        return "\n".join(lst)

    def get_func_def(self) -> Tuple["Argument", "TypeIns"]:
        return self.overloads[0].argument, self.overloads[0].ret_type

    def get_func_name(self):
        return self.funname

    def call(
        self, applyargs: "ApplyArgs", node: Optional[ast.AST]
    ) -> Option["TypeIns"]:
        # TODO: deal with overloads(find a best match)
        from pystatic.arg import match_argument

        assert self.overloads
        error_list = match_argument(self.overloads[0].argument, applyargs, node)
        ret_option = Option(self.overloads[0].ret_type)
        ret_option.add_err_list(error_list)
        return ret_option


func_temp = TypeFuncTemp()
module_temp = TypeModuleTemp()

any_temp = TypeAnyTemp()
any_ins = any_temp.get_default_ins().value
any_type = any_temp.get_default_typetype()
