import ast
import enum
import copy
from pystatic.symtable import Entry, SymTable
from typing import Optional, Dict, List, Tuple, Union, TYPE_CHECKING
from pystatic.uri import Uri

if TYPE_CHECKING:
    from pystatic.arg import Argument

TypeContext = Dict['TypeVar', 'TypeType']
TypeVarList = List['TypeVar']
BindList = List[Union['TypeType', List['TypeType'], 'TypeIns']]


class GetItemError(Exception):
    def __init__(self) -> None:
        self.msg: str = ''
        self.errors: List[Tuple[int, str]] = []

    def empty(self) -> bool:
        return not self.msg and not self.errors

    def add_error(self, index: int, msg: str):
        self.errors.append((index, msg))

    def set_msg(self, msg: str):
        self.msg = msg


class BaseType(object):
    def __init__(self, typename: str):
        self.name = typename

    @property
    def basename(self) -> str:
        rpos = self.name.rfind('.')
        return self.name[rpos + 1:]

    def __str__(self):
        """ Used for type hint """
        return self.name


class TpState(enum.IntEnum):
    FRESH = 0
    ON = 1
    OVER = 2


class TypeTemp(BaseType):
    def __init__(self, name: str, resolve_state: TpState = TpState.OVER):
        super().__init__(name)
        self.placeholders = []

        self._resolve_state = resolve_state

    def get_inner_typedef(self, name: str) -> Optional['TypeTemp']:
        return None

    def set_state(self, st: TpState):
        self._resolve_state = st

    def get_state(self) -> TpState:
        return self._resolve_state

    def _bind_placeholders(self,
                           bindlist: BindList) -> Tuple[list, 'GetItemError']:
        binderr: GetItemError = GetItemError()
        if len(bindlist) == 0:
            return [], binderr
        binderr.set_msg(f'No binding is allowed in {self.basename}')
        return [], binderr

    def generate_typetype(
            self, bindlist: BindList) -> Tuple['TypeType', 'GetItemError']:
        new_bind, bind_err = self._bind_placeholders(bindlist)
        return TypeType(self, new_bind), bind_err

    def get_default_type(self) -> 'TypeType':
        bind_type, bind_err = self.generate_typetype([])
        assert bind_err.empty(), "Get default type should always succeed"
        return bind_type

    def getattribute(
            self,
            name: str,
            bindlist: BindList,
            context: Optional[TypeContext] = None) -> Optional['TypeIns']:
        return None

    def setattr(self, name: str, attr_type: 'TypeIns'):
        assert 0, "This function should be avoided because TypeClassTemp doesn't support it"

    def getattr(self,
                name: str,
                bindlist: BindList,
                context: Optional[TypeContext] = None) -> Optional['TypeIns']:
        return self.getattribute(name, bindlist, context)

    def get_str_expr(self,
                     bindlist: BindList,
                     context: Optional[TypeContext] = None) -> str:
        return self.name


class TypeVar(TypeTemp):
    def __init__(self,
                 name: str,
                 *args: 'TypeIns',
                 bound: Optional['TypeIns'] = None,
                 covariant=False,
                 contravariant=False):
        super().__init__(name)
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


class TypeIns(BaseType):
    def __init__(self, temp: TypeTemp, bindlist: BindList):
        """bindlist will be shallowly copied"""
        super().__init__(temp.name)
        self.temp = temp
        self.bindlist = copy.copy(bindlist)

    def substitute(self, context: TypeContext) -> list:
        context = context or {}
        new_bindlist = []
        for item in self.bindlist:
            if isinstance(item, TypeVar) and item in context:
                # TODO: check consistence here
                new_bindlist.append(context[item])
            else:
                new_bindlist.append(item)
        return new_bindlist

    def shadow(self, context: TypeContext) -> TypeContext:
        new_context = {**context}
        for i, item in enumerate(self.bindlist):
            if len(self.temp.placeholders) > i:
                old_slot = self.temp.placeholders[i]
                if isinstance(old_slot, TypeVar) and old_slot in new_context:
                    assert isinstance(item, TypeType)
                    new_context[old_slot] = item
        return new_context

    def getattribute(
            self,
            name: str,
            context: Optional[TypeContext] = None) -> Optional['TypeIns']:
        context = context or {}
        context = self.shadow(context)
        return self.temp.getattribute(name, self.substitute(context), context)

    def getattr(self,
                name: str,
                context: Optional[TypeContext] = None) -> Optional['TypeIns']:
        return self.getattribute(name, context)

    def getitem(self, items) -> Tuple['TypeIns', 'GetItemError']:
        getitem_err = GetItemError()
        getitem_err.set_msg(f"{self.basename} doesn't support __getitem__")
        return (any_ins, getitem_err)

    def __str__(self) -> str:
        return self.name


class TypeType(TypeIns):
    def __init__(self, temp: TypeTemp, bindlist: BindList):
        super().__init__(temp, bindlist)

    def getins(self) -> 'TypeIns':
        return TypeIns(self.temp, self.bindlist)

    def call(self) -> 'TypeIns':
        return self.getins()

    def getitem(self, bindlist: BindList) -> Tuple['TypeType', 'GetItemError']:
        return self.temp.generate_typetype(bindlist)

    def setattr(self, name, tp):
        self.temp.setattr(name, tp)

    def __str__(self):
        return self.temp.get_str_expr([])


class TypeClassTemp(TypeTemp):
    # FIXME: remove None of symtable and defnode
    def __init__(self,
                 clsname: str,
                 state: TpState,
                 def_symtable: 'SymTable',
                 inner_symtable: 'SymTable',
                 defnode: ast.ClassDef = None):
        super().__init__(clsname, state)

        self.baseclass: 'List[TypeType]'
        self.baseclass = []

        self.var_attr: Dict[str, 'TypeIns'] = {}

        self._inner_symtable = inner_symtable  # symtable belongs to this cls
        self._def_symtable = def_symtable  # symtable where this cls is defined
        self._defnode = defnode

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

    def set_inner_symtable(self, symtable):
        self._inner_symtable = symtable

    def get_inner_symtable(self) -> 'SymTable':
        return self._inner_symtable

    def get_def_symtable(self) -> 'SymTable':
        assert self._def_symtable
        return self._def_symtable

    def get_defnode(self) -> ast.ClassDef:
        assert self._defnode
        return self._defnode

    def add_typevar(self, typevar: TypeVar):
        self.placeholders.append(typevar)

    def add_base(self, basetype: 'TypeType'):
        if basetype not in self.baseclass:
            self.baseclass.append(basetype)

    def _bind_placeholders(self,
                           bindlist) -> Tuple[TypeContext, 'GetItemError']:
        binderr: GetItemError = GetItemError()
        binds: TypeContext = {}
        if not bindlist:  # empty bindlist implies each is Any
            return binds, binderr  # NOTE: this may be wrong
        else:
            supply = []
            if len(bindlist) != len(self.placeholders):
                binderr.set_msg(
                    f'{self.basename} require {len(self.placeholders)} but {len(bindlist)} given'
                )
                # error recovery:
                # if bindlist is shorter than.placeholders, then extend bindlist with Any.
                # if bindlist is longer than.placeholders, then trucate it(through zip).
                if len(bindlist) < len(self.placeholders):
                    supply = [any_type
                              ] * (len(self.placeholders) - len(bindlist))

            cnt = 0
            for tpvar, tpbind in zip(self.placeholders, bindlist + supply):
                if not isinstance(tpbind, TypeType):
                    binderr.add_error(cnt, f'require a type')
                    tpbind = any_type

                binds[tpvar] = tpbind
                cnt += 1

            return binds, binderr

    def add_var(self, name: str, var_type: 'TypeIns'):
        self.var_attr[name] = var_type

    def get_local_attr(
            self,
            name: str,
            binds: Optional[TypeContext] = None) -> Optional['TypeIns']:
        if name in self.var_attr:
            return self.var_attr[name]
        else:
            return self._inner_symtable.lookup_local(name)

    def setattr(self, name: str, attr_type: 'TypeIns'):
        """Same as add_var in TypeClassTemp"""
        self.add_var(name, attr_type)

    def getattribute(self, name: str, bindlist: BindList,
                     context: Optional[TypeContext]) -> Optional['TypeIns']:
        # FIXME: current implementation doesn't cope bindlist, context and baseclasses
        res = self.get_local_attr(name)
        return res


class TypeFuncTemp(TypeTemp):
    def __init__(self, name: str, inner_symtable: 'SymTable',
                 argument: 'Argument', ret: TypeIns) -> None:
        self.name = name
        self.argument = argument
        self.ret = ret

        self._inner_symtable = inner_symtable

    def get_inner_symtable(self) -> 'SymTable':
        return self._inner_symtable

    def get_str_expr(self,
                     bindlist: BindList,
                     context: Optional[TypeContext] = None) -> str:
        return self.name + str(self.argument) + ' -> ' + str(self.ret)


class TypeModuleTemp(TypeClassTemp):
    def __init__(self, uri: Uri, symtable: 'SymTable', state: TpState):
        # FIXME: inner_symtable and def_symtable should be different
        super().__init__(uri, state, symtable, symtable)

    @property
    def uri(self):
        return self.name

    def get_inner_typedef(self, name: str) -> Optional['TypeTemp']:
        return self._inner_symtable.get_type_def(name)


class TypePackageTemp(TypeModuleTemp):
    def __init__(self, paths: List[str], uri: Uri):
        assert 0, "not implemented yet"
        super().__init__(uri)
        self.paths = paths


class TypeAnyTemp(TypeTemp):
    def __init__(self):
        super().__init__('Any')

    def get_default_type(self) -> 'TypeType':
        return any_type

    def has_method(self, name: str) -> bool:
        return True

    def has_attribute(self, name: str) -> bool:
        return True


class TypeNoneTemp(TypeTemp):
    def __init__(self):
        super().__init__('None')

    def get_default_type(self) -> 'TypeType':
        return none_type

    def has_method(self, name: str) -> bool:
        return False

    def has_attribute(self, name: str) -> bool:
        return False


class TypeTupleTemp(TypeTemp):
    def __init__(self):
        super().__init__('Tuple')


class TypeDictTemp(TypeTemp):
    def __init__(self):
        super().__init__('Dict')


class TypeUnionTemp(TypeTemp):
    def __init__(self):
        super().__init__('Union')


class TypeOptionalTemp(TypeTemp):
    def __init__(self):
        super().__init__('Optional')


class TypeEllipsisTemp(TypeTemp):
    def __init__(self) -> None:
        super().__init__('ellipsis')

    def get_default_type(self) -> 'TypeType':
        return ellipsis_type


class TypeCallableTemp(TypeTemp):
    def __init__(self):
        super().__init__('Callable')

    def _bind_placeholders(self,
                           bindlist: BindList) -> Tuple[list, 'GetItemError']:
        binderr = GetItemError()
        new_bindlist: BindList = []
        if not bindlist:
            return [], binderr

        # argument part
        if isinstance(bindlist[0], list):
            param_list: List[TypeType] = []
            for i, item in enumerate(bindlist[0]):  # type: ignore
                if not isinstance(item, TypeType):
                    assert isinstance(item, TypeIns)
                    binderr.add_error(i, f'{item.basename} is not a type')
                    param_list.append(any_type)
                else:
                    param_list.append(item)
            new_bindlist.append(param_list)
        else:
            is_ellipsis = False
            if isinstance(bindlist[0], TypeType):
                temp = bindlist[0].temp  # type: ignore
                if isinstance(temp, TypeEllipsisTemp):
                    new_bindlist.append(bindlist[0])
                    is_ellipsis = True
            if not is_ellipsis:
                binderr.add_error(
                    0, f'the first argument should be a list or ...')
                new_bindlist.append(ellipsis_type)  # default: ellipsis

        # return type part
        if len(bindlist) >= 2:
            if isinstance(bindlist[1], TypeType):
                new_bindlist.append(bindlist[1])
            else:
                binderr.add_error(1, f'a type is required')
                new_bindlist.append(any_type)  # default return type: Any

            if len(bindlist) > 2:
                binderr.set_msg('only two arguments are required')
        else:
            binderr.set_msg('require two arguments')
            new_bindlist.append(any_type)

        return new_bindlist, binderr


class TypeGenericTemp(TypeTemp):
    def __init__(self):
        super().__init__('typing.Generic')

    def _bind_placeholders(self,
                           bindlist: BindList) -> Tuple[list, 'GetItemError']:
        binderr: GetItemError = GetItemError()
        new_bindlist = []
        for i, bind_item in enumerate(bindlist):
            if isinstance(bind_item, TypeType) and isinstance(
                    bind_item.temp, TypeVar):
                new_bindlist.append(bind_item)
            else:
                assert 0, "For temporary test"
                binderr.add_error(i, f'a type is required')
        return new_bindlist, binderr


class TypeLiteralTemp(TypeTemp):
    def __init__(self) -> None:
        super().__init__('typing.Literal')


# special types
any_temp = TypeAnyTemp()
none_temp = TypeNoneTemp()
generic_temp = TypeGenericTemp()
ellipsis_temp = TypeEllipsisTemp()
callable_temp = TypeCallableTemp()
tuple_temp = TypeTupleTemp()
optional_temp = TypeOptionalTemp()
literal_temp = TypeLiteralTemp()
union_temp = TypeUnionTemp()

# these typetype are shared to save memory
ellipsis_type, _ = ellipsis_temp.generate_typetype([])
none_type, _ = none_temp.generate_typetype([])
any_type, _ = any_temp.generate_typetype([])

any_ins = any_type.call()
ellipsis_ins = ellipsis_type.call()
