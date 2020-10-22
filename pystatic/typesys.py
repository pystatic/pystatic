import ast
import enum
import copy
from typing import (Optional, Dict, List, Tuple, Union, TYPE_CHECKING, Final)
from pystatic.option import Option
from pystatic.uri import Uri
from pystatic.evalutil import (InsWithAst, ApplyArgs, GetItemType, WithAst)
from pystatic.symtable import Entry, SymTable
from pystatic.errorcode import NoAttribute

if TYPE_CHECKING:
    from pystatic.arg import Argument

TypeContext = Dict['TypeVarIns', 'TypeType']
TypeVarList = List['TypeVarIns']
BindList = Optional[List[Union['TypeType', List['TypeType'], 'TypeIns']]]

DEFAULT_TYPEVAR_NAME: Final[str] = '__unknown_typevar_name__'


class TpVarKind(enum.IntEnum):
    INVARIANT = 0
    COVARIANT = 1
    CONTRAVARIANT = 2


class TpState(enum.IntEnum):
    FRESH = 0
    ON = 1
    OVER = 2


class TypeTemp:
    def __init__(self,
                 name: str,
                 module_uri: str,
                 resolve_state: TpState = TpState.OVER):
        self.name = name
        self.placeholders = []

        self.module_uri = module_uri  # the module uri that define this type
        self._resolve_state = resolve_state

    @property
    def basename(self) -> str:
        rpos = self.name.rfind('.')
        return self.name[rpos + 1:]

    def get_inner_typedef(self, name: str) -> Optional['TypeTemp']:
        return None

    def get_typetype(self,
                     bindlist: Optional[BindList] = None,
                     item: Optional[GetItemType] = None) -> Option['TypeType']:
        """Mainly used for TypeType to generate correct TypeType"""
        if not item:
            return Option(TypeType(self, None))
        else:
            if isinstance(item.ins, (tuple, list)):
                tpins_list = []
                for item in item.ins:
                    if isinstance(item.ins, TypeIns):
                        tpins_list.append(item.ins)
                    else:
                        # TODO: add warning here
                        pass
                return Option(TypeType(self, tpins_list))
            else:
                if isinstance(item.ins, TypeIns):
                    return Option(TypeType(self, [item.ins]))
                else:
                    # TODO: add warning here
                    return Option(TypeType(self, None))

    def get_default_typetype(self) -> 'TypeType':
        return self.get_typetype(None, None).value

    def getins(self, bindlist: BindList) -> 'TypeIns':
        return TypeIns(self, bindlist)

    def get_default_ins(self) -> 'TypeIns':
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
        return Option(self.getins(bindlist))

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

    # string expression
    def str_expr(self,
                 bindlist: BindList,
                 context: Optional[TypeContext] = None) -> str:
        """__str__ with bindlist and context"""
        return self.name

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
            if isinstance(item, TypeVarTemp) and item in context:
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

    def __str__(self) -> str:
        return self.temp.str_expr(self.bindlist)


class TypeType(TypeIns):
    def __init__(self, temp: TypeTemp, bindlist: BindList):
        super().__init__(temp, bindlist)

    def getins(self) -> 'TypeIns':
        return self.temp.getins(self.bindlist)

    def call(self, args) -> 'TypeIns':
        return self.getins()

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
        if s == "Any":
            return s
        else:
            return "type(" + s + ')'


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
                default_ins.constrains.append(rangenode.ins.getins())

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
                 module_uri: str,
                 state: TpState,
                 def_symtable: 'SymTable',
                 inner_symtable: 'SymTable',
                 defnode: ast.ClassDef = None):
        super().__init__(clsname, module_uri, state)

        self.baseclass: 'List[TypeType]'
        self.baseclass = []

        self.var_attr: Dict[str, 'TypeIns'] = {}

        self._inner_symtable = inner_symtable  # symtable belongs to this cls
        self._def_symtable = def_symtable  # symtable where this cls is defined
        self._defnode = defnode

        self._glob_uri = module_uri  # the module uri that this class is defined

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
    def __init__(self, uri: Uri, symtable: 'SymTable'):
        # FIXME: inner_symtable and def_symtable should be different
        super().__init__(uri, uri, TpState.OVER, symtable, symtable)

    @property
    def uri(self):
        return self.name

    def get_inner_typedef(self, name: str) -> Optional['TypeTemp']:
        return self._inner_symtable.get_type_def(name)


class TypePackageTemp(TypeModuleTemp):
    def __init__(self, paths: List[str], symtable: 'SymTable', uri: Uri):
        super().__init__(uri, symtable)
        self.paths = paths

    def get_default_typetype(self) -> 'TypeType':
        return TypePackageType(self)


class TypeAnyTemp(TypeTemp):
    def __init__(self):
        super().__init__('Any', 'typing')

    def get_default_typetype(self) -> 'TypeType':
        return any_type

    def get_default_ins(self) -> 'TypeIns':
        return any_ins

    def getins(self, bindlist: BindList) -> 'TypeIns':
        return any_ins


class TypeNoneTemp(TypeTemp):
    def __init__(self):
        super().__init__('None', 'typing')

    def get_default_typetype(self) -> 'TypeType':
        return none_type

    def has_method(self, name: str) -> bool:
        return False

    def has_attribute(self, name: str) -> bool:
        return False


class TypeTupleTemp(TypeTemp):
    def __init__(self):
        super().__init__('Tuple', 'typing')


class TypeDictTemp(TypeTemp):
    def __init__(self):
        super().__init__('Dict', 'typing')


class TypeUnionTemp(TypeTemp):
    def __init__(self):
        super().__init__('Union', 'typing')


class TypeOptionalTemp(TypeTemp):
    def __init__(self):
        super().__init__('Optional', 'typing')


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


class TypeLiteralIns(TypeIns):
    def __init__(self, value):
        super().__init__(literal_temp, None)
        self.value = value

    def __str__(self):
        return type(self.value).__name__


class TypePackageType(TypeType):
    def __init__(self, temp: TypePackageTemp) -> None:
        super().__init__(temp, None)

    def getins(self) -> 'TypeIns':
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


class TypeFuncIns(TypeIns):
    def __init__(self, funname: str, module_uri: str,
                 inner_symtable: 'SymTable', argument: 'Argument',
                 ret: TypeIns) -> None:
        super().__init__(func_temp, None)
        self.overloads: List[Tuple['Argument', TypeIns]] = [(argument, ret)]
        self.funname = funname
        self.module_uri = module_uri

        self._inner_symtable = inner_symtable

    def add_overload(self, argument: 'Argument', ret: TypeIns):
        self.overloads.append((argument, ret))

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
            fun_fmt.format(self.funname, argument, ret)
            for argument, ret in self.overloads
        ]
        return '\n'.join(lst)

    def call(self, applyargs: 'ApplyArgs') -> Option['TypeIns']:
        # TODO: deal with arguments
        assert self.overloads
        return Option(self.overloads[0])


# special types (typing.py)
any_temp = TypeAnyTemp()
none_temp = TypeNoneTemp()
generic_temp = TypeGenericTemp()
ellipsis_temp = TypeEllipsisTemp()
callable_temp = TypeCallableTemp()
tuple_temp = TypeTupleTemp()
optional_temp = TypeOptionalTemp()
literal_temp = TypeLiteralTemp()
union_temp = TypeUnionTemp()
typevar_temp = TypeVarTemp()

# builtins.py
func_temp = TypeFuncTemp()

# these typetype are shared to save memory
ellipsis_type = TypeType(ellipsis_temp, None)
none_type = TypeType(none_temp, None)
any_type = TypeType(any_temp, None)
typevar_type = TypeType(typevar_temp, None)

any_ins = TypeIns(any_temp, None)
ellipsis_ins = TypeIns(ellipsis_temp, None)
