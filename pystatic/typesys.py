import ast
import enum
import copy
from typing import Callable, Optional, Dict, List, Tuple, Union, TYPE_CHECKING
from pystatic.option import Option
from pystatic.symtable import Entry, SymTable
from pystatic.message import MessageBox
from pystatic.uri import Uri

if TYPE_CHECKING:
    from pystatic.arg import Argument

TypeContext = Dict['TypeVar', 'TypeType']
TypeVarList = List['TypeVar']
BindList = Optional[List[Union['TypeType', List['TypeType'], 'TypeIns']]]


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

    def set_state(self, st: TpState):
        self._resolve_state = st

    def get_state(self) -> TpState:
        return self._resolve_state

    def get_typetype(self, bindlist: BindList) -> 'TypeType':
        new_bind = None  # TODO: rename this
        return TypeType(self, new_bind)

    def get_default_typetype(self) -> 'TypeType':
        return self.get_typetype(None)

    def getins(self, bindlist: BindList) -> 'TypeIns':
        return TypeIns(self, bindlist)

    def get_default_ins(self) -> 'TypeIns':
        return self.getins(None)

    def getattribute(
            self,
            name: str,
            node: ast.AST,
            mbox: MessageBox,
            bindlist: BindList,
            context: Optional[TypeContext] = None) -> Option['TypeIns']:
        return Option(False, any_ins)

    def setattr(self, name: str, attr_type: 'TypeIns'):
        assert 0, "This function should be avoided because TypeClassTemp doesn't support it"

    def getattr(self,
                name: str,
                node: ast.AST,
                mbox: MessageBox,
                bindlist: BindList,
                context: Optional[TypeContext] = None) -> Option['TypeIns']:
        return self.getattribute(name, node, mbox, bindlist, context)

    def str_expr(self,
                 bindlist: BindList,
                 context: Optional[TypeContext] = None) -> str:
        """__str__ with bindlist and context"""
        return self.name

    def __str__(self):
        return self.name


class TypeVar(TypeTemp):
    def __init__(self,
                 name: str,
                 module_uri: str,
                 *args: 'TypeIns',
                 bound: Optional['TypeIns'] = None,
                 covariant=False,
                 contravariant=False):
        super().__init__(module_uri, name)
        self.bound = bound
        if contravariant:
            self.covariant = False
        else:
            self.covariant = covariant
        if contravariant or covariant:
            self.invariant = False
        else:
            self.invariant = True
        self.contravariant = contravariant
        self.constrains: List['TypeIns'] = list(*args)


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
            if isinstance(item, TypeVar) and item in context:
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
                if isinstance(old_slot, TypeVar) and old_slot in new_context:
                    assert isinstance(item, TypeType)
                    new_context[old_slot] = item
        return new_context

    def getattribute(
            self,
            name: str,
            node: ast.AST,
            mbox: MessageBox,
            context: Optional[TypeContext] = None) -> Option['TypeIns']:
        context = context or {}
        context = self.shadow(context)
        return self.temp.getattribute(name, node, mbox,
                                      self.substitute(context), context)

    def getattr(self,
                name: str,
                node: ast.AST,
                mbox: MessageBox,
                context: Optional[TypeContext] = None) -> Option['TypeIns']:
        return self.getattribute(name, node, mbox, context)

    def getitem(self, items) -> 'TypeIns':
        assert False, "TODO"

    def __str__(self) -> str:
        return self.temp.str_expr(self.bindlist)

    def call(self, args):
        assert False, "TODO"

    def get_local_symbol(self, name: str) -> 'TypeIns':
        return self.temp.get_local_symbol(name)


class TypeType(TypeIns):
    def __init__(self, temp: TypeTemp, bindlist: BindList):
        super().__init__(temp, bindlist)

    def getins(self) -> 'TypeIns':
        return self.temp.getins(self.bindlist)

    def call(self, args) -> 'TypeIns':
        return self.getins()

    def getattribute(self,
                     name: str,
                     node: ast.AST,
                     mbox: MessageBox,
                     context: Optional[TypeContext] = None) -> Optional['TypeIns']:
        context = context or {}
        context = self.shadow(context)
        return self.temp.get_local_symbol

    def getitem(self, bindlist: BindList) -> 'TypeIns':
        assert False, "TODO"

    def setattr(self, name, tp):
        self.temp.setattr(name, tp)

    def __str__(self):
        return self.temp.str_expr(None)


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

    def _add_defer_var(self, name, attrs):
        """Defer attribute type evaluation.

        Never use this unless you have a good reason.
        """
        self.var_attr[name] = attrs

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

    def setattr(self, name: str, attr_type: 'TypeIns'):
        if name in self.var_attr:
            self.var_attr[name] = attr_type
        else:
            self._inner_symtable.set_local_type(name, attr_type)

    def getattribute(self, name: str, node: ast.AST, mbox: MessageBox,
                     bindlist: BindList,
                     context: Optional[TypeContext]) -> Option['TypeIns']:
        res = self.get_local_attr(name)
        if not res:
            for basecls in self.baseclass:
                res = basecls.getattribute(name, node, mbox)
                if res:
                    return res

        if res:
            return Option(True, res)
        else:
            return Option(False, any_ins)

    def get_local_symbol(self, name: str) -> 'TypeIns':
        return self._inner_symtable.lookup_local(name)


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


class TypeLiteralTemp(TypeTemp):
    def __init__(self) -> None:
        super().__init__('Literal', 'typing')


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

    def get_str_expr(self,
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

    def call(self, args):
        assert False, "TODO"

    def lookup_local_var(self, name):
        return self._inner_symtable.lookup_local(name)

    def lookup_var(self, name):
        return self._inner_symtable.egb_lookup(name)


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

# builtins.py
func_temp = TypeFuncTemp()

# these typetype are shared to save memory
ellipsis_type = TypeType(ellipsis_temp, None)
none_type = TypeType(none_temp, None)
any_type = TypeType(any_temp, None)

any_ins = TypeIns(any_temp, None)
ellipsis_ins = TypeIns(ellipsis_temp, None)
