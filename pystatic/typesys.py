import copy
from abc import ABC, abstractmethod
from typing import Any, Final, Dict, Type
from pystatic.result import Result
from pystatic.opmap import get_funname, get_opstr
from pystatic.error.errorcode import *

if TYPE_CHECKING:
    from pystatic.symtable import SymTable, FunctionSymTable
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

    def get_local_attr(self, name: str, node: Optional[ast.AST]) -> Optional["TypeIns"]:
        return self.temp.get_local_attr(name, self.bindlist)

    def getattribute(self, name: str, node: Optional[ast.AST]) -> Result["TypeIns"]:
        result = Result(any_ins)
        ins_res = self.temp.getattribute(name, self.bindlist)

        if not ins_res:
            result.add_err(NoAttribute(node, self, name))
        else:
            result.set_value(ins_res)
        return result

    def getattr(self, name: str, node: Optional[ast.AST]) -> Result["TypeIns"]:
        return self.getattribute(name, node)

    def call(
        self, applyargs: "ApplyArgs", node: Optional[ast.Call]
    ) -> Result["TypeIns"]:
        return self.temp.call(applyargs, self, node)

    def getitem(
        self, item: "GetItemArgs", node: Optional[ast.AST] = None
    ) -> Result["TypeIns"]:
        # TODO: add error
        return self.temp.getitem(item, self.bindlist, node)

    def get_safe_bind(self, i: int):
        """Get ith bind element with implicit any"""
        if self.bindlist:
            try:
                return self.bindlist[i]
            except IndexError:
                return any_ins
        return any_ins

    def unaryop_mgf(self, op: Type, node: ast.AST) -> Result["TypeIns"]:
        """
        @param op: type of the operator.

        @param node: ast node represents this operation.
        """
        return self.temp.unaryop_mgf(self, op, node)

    def binop_mgf(self, other: "TypeIns", op: Type, node: ast.AST) -> Result["TypeIns"]:
        """
        @param other: second operator.

        @param op: type of the operator.

        @param node: ast node represents this operation.
        """
        return self.temp.binop_mgf(self, other, op, node)

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

    def getins(self, typetype_result: Result["TypeIns"]) -> "TypeIns":
        """Get TypeIns from TypeType

        all errors will be stored in typetype_result.
        """
        ins_result = self.temp.getins(self.bindlist)
        typetype_result.combine_error(ins_result)

        return ins_result.value

    def get_default_ins(self) -> "TypeIns":
        """Get TypeIns from TypeType"""
        ins_result = self.temp.getins(self.bindlist)
        return ins_result.value

    def getattribute(self, name: str, node: Optional[ast.AST]) -> Result["TypeIns"]:
        result = Result(any_ins)
        ins_res = self.temp.get_type_attribute(name, self.bindlist)

        if not ins_res:
            err = NoAttribute(node, self, name)
            result.add_err(err)
        else:
            result.set_value(ins_res)
        return result

    def getitem(
        self, item: "GetItemArgs", node: Optional[ast.AST] = None
    ) -> Result["TypeIns"]:
        return self.temp.getitem_typetype(self.bindlist, item, node)

    def call(
        self, applyargs: "ApplyArgs", node: Optional[ast.Call]
    ) -> Result["TypeIns"]:
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

    def get_mro(self):
        return [self.get_default_ins()]

    # basic
    def get_local_attr(self, name: str, bindlist: BindList) -> Optional["TypeIns"]:
        return None

    def getattribute(self, name: str, bindlist: BindList) -> Optional["TypeIns"]:
        return None

    def getattr(self, name: str, bindlist: BindList) -> Optional["TypeIns"]:
        return self.getattribute(name, bindlist)

    def call(
        self, applyargs: "ApplyArgs", typeins: "TypeIns", node: Optional[ast.Call]
    ) -> Result["TypeIns"]:
        result = Result(any_ins)
        call_func = self.getattribute("__call__", typeins.bindlist)
        if not call_func or call_func.temp != func_temp:
            result.add_err(NotCallable(typeins, node))
        else:
            result = call_func.call(applyargs, node)
        return result

    def getitem(
        self, item: "GetItemArgs", bindlist: BindList, node: Optional[ast.AST]
    ) -> Result["TypeIns"]:
        result = Result(any_ins)
        # TODO: add error
        return result

    # magic operation functions(mgf is short for magic function).
    def unaryop_mgf(
        self, typeins: "TypeIns", op: Type, node: ast.AST
    ) -> Result["TypeIns"]:
        from pystatic.evalutil import ApplyArgs

        result = Result(any_ins)
        func_name = get_funname(op)
        assert func_name, f"{func_name} is not supported now"
        func = self.getattribute(func_name, typeins.bindlist)
        if not func or not isinstance(func, TypeFuncIns):
            op_str = get_opstr(op)
            assert op_str
            result.add_err(OperationNotSupported(op_str, typeins, node))
            return result

        else:
            applyargs = ApplyArgs()
            applyargs.add_arg(typeins, node)  # self argument
            return func.call(applyargs, node)

    def binop_mgf(
        self, typeins: "TypeIns", other: "TypeIns", op: Type, node: ast.AST
    ) -> Result["TypeIns"]:
        from pystatic.evalutil import ApplyArgs

        result = Result(any_ins)
        func_name = get_funname(op)
        assert func_name, f"{func_name} is not supported now"
        func = self.getattribute(func_name, typeins.bindlist)
        if not func or not isinstance(func, TypeFuncIns):
            op_str = get_opstr(op)
            assert op_str
            result.add_err(OperationNotSupported(op_str, typeins, node))
            return result

        else:
            applyargs = ApplyArgs()
            applyargs.add_arg(typeins, node)  # self argument
            applyargs.add_arg(other, node)
            return func.call(applyargs, node)

    # some helper methods
    def get_inner_typedef(self, name: str) -> Optional["TypeTemp"]:
        return None

    def _getitem_typetype_check_bindlist(self, bindlist, result: Result, node) -> bool:
        if bindlist is not None:
            result.add_err(NotSubscriptable(TypeIns(self, bindlist), node))
            return False
        return True

    def _getitem_typetype_check_arity(
        self, itemarg: "GetItemArgs", result: Result, node
    ) -> bool:
        items = itemarg.items
        len_items = len(items)
        assert len_items > 0
        arity = self.arity()
        if arity == INFINITE_ARITY:
            return True
        elif arity != len_items:
            # TODO: many false positive
            result.add_err(IndiceParamNumberMismatch(len_items, arity, node))
            return False
        else:
            return True

    def _getitem_typetype_accept_item(
        self, item: "WithAst", result: Result, res_bindlist: BindList
    ):
        value = item.value
        node = item.node
        if not isinstance(value, TypeIns):
            result.add_err(IndiceParamNotClass(node))
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
                result.add_err(IndiceParamNotClass(node))
            res_bindlist.append(value)
        else:
            res_bindlist.append(value.get_default_ins())

    def getitem_typetype(
        self, bindlist: BindList, itemarg: "GetItemArgs", node: Optional[ast.AST] = None
    ) -> Result["TypeType"]:
        """Mainly used for TypeType to generate correct TypeType"""
        res_bindlist = []
        result = Result(TypeType(self, res_bindlist))

        if not self._getitem_typetype_check_bindlist(bindlist, result, node):
            result.value = TypeType(self, bindlist)
            return result
        self._getitem_typetype_check_arity(itemarg, result, node)

        if self.arity() == INFINITE_ARITY:
            len_items = len(itemarg.items)
        else:
            len_items = min(self.arity(), len(itemarg.items))
        pad_cnt = max(self.arity() - len_items, 0)
        for i in range(len_items):
            self._getitem_typetype_accept_item(itemarg.items[i], result, res_bindlist)
        res_bindlist.extend([any_ins] * pad_cnt)
        return result

    def get_default_typetype(self) -> "TypeType":
        return self._cached_typetype

    def getins(self, bindlist: BindList) -> Result["TypeIns"]:
        if self.arity == 0 or not bindlist:
            return Result(self._cached_ins)
        else:
            return Result(TypeIns(self, bindlist))

    def get_default_ins(self) -> "TypeIns":
        return self._cached_ins

    def get_type_attribute(self, name: str, bindlist: BindList) -> Optional["TypeIns"]:
        """Get attribute that belong to the Type itself, mainly used for TypeType"""
        return self.getattribute(name, bindlist)

    def init_ins(self, applyargs: "ApplyArgs", bindlist: BindList) -> Result["TypeIns"]:
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

    Mainly used for test

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
        self.mro: Optional[List[TypeIns]] = None

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

    def get_local_attr(self, name: str, bindlist: BindList) -> Optional["TypeIns"]:
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

    def get_mro(self):
        """C3 algorithm"""
        from pystatic.predefined import object_temp

        # TODO: avoid recursion
        # TODO: report error if C3 fails

        # type parameter is not concerned
        if self.mro is not None:
            return list(self.mro)  # copy of self.mro
        to_merge = []
        for base in self.baseclass:
            base_mro = base.temp.get_mro()
            if base_mro:
                to_merge.append(base_mro)

        if self.baseclass:
            to_merge.append(list(self.baseclass))  # append a copy of baseclasses
        cur_ans = []
        while to_merge:
            listlen = len(to_merge)
            for i in range(listlen):
                head = to_merge[i][0]
                for j in range(i + 1, listlen):
                    for iter_ins in to_merge[j][1:]:
                        if head.equiv(iter_ins):
                            break
                else:
                    cur_ans.append(head)
                    for j in range(listlen):
                        leniter = len(to_merge[j])
                        for iter_cnt in range(leniter):
                            if head.equiv(to_merge[j][iter_cnt]):
                                to_merge[j].pop(iter_cnt)
                                break
                    break
            new_to_merge = [x for x in to_merge if x]
            to_merge = new_to_merge

        self.mro = [self.get_default_ins()] + cur_ans
        if self.mro[-1].temp is object_temp:
            self.mro = self.mro[:-1]
        return list(self.mro)  # copy of self.mro

    def getattribute(self, name: str, bindlist: BindList) -> Optional["TypeIns"]:
        res = self.get_local_attr(name, bindlist)
        if not res:
            assert self.mro is not None
            if self.mro:
                for basecls in self.mro[1:]:
                    res = basecls.get_local_attr(name, None)
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
    ) -> Result["TypeIns"]:
        return Result(self._cached_ins)

    def getitem(
        self,
        item: "GetItemArgs",
        bindlist: BindList,
        node: Optional[ast.AST] = None,
    ) -> Result["TypeIns"]:
        return Result(self._cached_ins)

    # magic operation functions
    def unaryop_mgf(
        self, typeins: "TypeIns", op: Type, node: ast.AST
    ) -> Result["TypeIns"]:
        return Result(self._cached_ins)

    def binop_mgf(
        self, typeins: "TypeIns", other: "TypeIns", op: Type, node: ast.AST
    ) -> Result["TypeIns"]:
        return Result(self._cached_ins)

    # some helper functions
    def getins(self, bindlist: BindList) -> Result["TypeIns"]:
        return Result(self._cached_ins)

    def getitem_typetype(
        self, bindlist: BindList, item: "GetItemArgs", node: Optional[ast.AST] = None
    ) -> Result["TypeType"]:
        # TODO: warning: if bindlist is non-empty, then report an error
        return Result(self._cached_typetype)

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
        inner_symtable: "FunctionSymTable",
        argument: "Argument",
        ret: TypeIns,
    ) -> None:
        super().__init__(func_temp, None)
        self.overloads: List[OverloadItem] = [OverloadItem(argument, ret)]
        self.funname = funname
        self.module_symid = module_symid

        self._inner_symtable = inner_symtable
        self._inner_symtable.param = argument

    def add_overload(self, argument: "Argument", ret: TypeIns):
        self.overloads.append(OverloadItem(argument, ret))

    def get_inner_symtable(self) -> "FunctionSymTable":
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
    ) -> Result["TypeIns"]:
        # TODO: deal with overloads(find a best match)
        from pystatic.arg import match_argument

        assert self.overloads
        error_list = match_argument(self.overloads[0].argument, applyargs, node)
        ret_result = Result(self.overloads[0].ret_type)
        ret_result.add_err_list(error_list)
        return ret_result


any_temp = TypeAnyTemp()
any_ins = any_temp.get_default_ins()
any_type = any_temp.get_default_typetype()

func_temp = TypeFuncTemp()
module_temp = TypeModuleTemp()
