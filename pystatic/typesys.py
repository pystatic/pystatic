import ast
import copy
from typing import Optional, Dict, List, Tuple, Union, Set, TYPE_CHECKING
from collections import OrderedDict
from pystatic.moduri import ModUri

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


class TypeTemp(BaseType):
    def __init__(self, name: str):
        super().__init__(name)
        self.placeholders = []

    def _bind_placeholders(self,
                           bindlist: BindList) -> Tuple[list, 'GetItemError']:
        """Do some check here, return a list that different from the bindlist"""
        binderr: GetItemError = GetItemError()
        if len(bindlist) == 0:
            return [], binderr
        binderr.set_msg(f'No binding is allowed in {self.basename}')
        return [], binderr

    def get_type(self,
                 bindlist: BindList) -> Tuple['TypeType', 'GetItemError']:
        """Usually you should make sure when binded and bindlist both are empty
        then it will not fail.

        May throw BindException."""
        new_bind, bind_err = self._bind_placeholders(bindlist)
        return TypeType(self, new_bind), bind_err

    def get_default_type(self) -> 'TypeType':
        bind_type, bind_err = self.get_type([])
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


class TypeVar(TypeTemp):
    def __init__(self,
                 name: str,
                 *args: 'TypeIns',
                 bound: Optional['Entry'] = None,
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
        self.constrains: List['Entry'] = list(*args)


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
        return self.temp.get_type(bindlist)


class TypeClassTemp(TypeTemp):
    def __init__(self, clsname: str):
        super().__init__(clsname)

        self.baseclass: 'OrderedDict[str, Entry]'
        self.baseclass = OrderedDict()

        self.cls_attr: Dict[str, 'Entry'] = {}
        self.var_attr: Dict[str, 'Entry'] = {}
        self.method: Dict[str, 'Entry'] = {}

    def add_typevar(self, typevar: TypeVar):
        self.placeholders.append(typevar)

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

    def add_base(self, name: str, entry: 'Entry'):
        self.baseclass[name] = entry

    def add_method(self, name: str, method_type: 'Entry'):
        self.method[name] = method_type

    def add_var(self, name: str, entry: 'Entry'):
        self.var_attr[name] = entry

    def add_clsvar(self, name: str, entry: 'Entry'):
        self.cls_attr[name] = entry

    def get_local_attr(
            self,
            name: str,
            binds: Optional[TypeContext] = None) -> Optional['TypeIns']:
        if name in self.var_attr:
            return self.var_attr[name].get_type()
        elif name in self.cls_attr:
            return self.cls_attr[name].get_type()
        return None

    def setattr(self, name: str, attr_type: 'TypeIns'):
        assert 0, "This function should not be called, use add_var or add_clsvar instead"
        self.add_clsvar(name, Entry(attr_type))

    def getattribute(self, name: str, bindlist: BindList,
                     context: Optional[TypeContext]) -> Optional['TypeIns']:
        # FIXME: current implementation doesn't cope bindlist, context and baseclasses
        res = self.get_local_attr(name)
        if not res:
            for base_entry in self.baseclass.values():
                basecls = base_entry.get_real_type()
                if isinstance(basecls, TypeType):
                    res = basecls.temp.getattribute(name, bindlist, context)
                    if res:
                        return res
        return res


class TypeModuleTemp(TypeClassTemp):
    def __init__(self, uri: ModUri, types: Dict[str, TypeTemp],
                 local: Dict[str, TypeIns]):
        super().__init__(uri)
        assert 0, "not implemented yet"
        # for tpname in types.keys():
        #     tpres = types[tpname].get_default_type()
        #     assert tpres
        #     if tpres:
        #         self.cls_attr[tpname] = tpres
        # self.cls_attr.update(local)

    @property
    def uri(self):
        return self.name


class TypePackageTemp(TypeModuleTemp):
    def __init__(self, paths: List[str], uri: ModUri, tp: Dict[str, TypeTemp],
                 local: Dict[str, TypeIns]):
        super().__init__(uri, tp, local)
        self.paths = paths


class TypeAnyTemp(TypeTemp):
    def __init__(self):
        super().__init__('Any')

    def has_method(self, name: str) -> bool:
        return True

    def has_attribute(self, name: str) -> bool:
        return True


class TypeNoneTemp(TypeTemp):
    def __init__(self):
        super().__init__('None')

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
        super().__init__('Generic')


class TypeDummyTemp(TypeTemp):
    """dummy type that used for test"""
    def __init__(self) -> None:
        typevarlist = []
        for i in range(5):
            typevarlist.append(TypeVar('T' + f'{i}'))
        super().__init__('dummy')

    def _bind_placeholders(self,
                           bindlist: BindList) -> Tuple[list, 'GetItemError']:
        return copy.copy(bindlist), GetItemError()


# default types
any_temp = TypeAnyTemp()
none_temp = TypeNoneTemp()
generic_temp = TypeGenericTemp()
ellipsis_temp = TypeEllipsisTemp()
callable_temp = TypeCallableTemp()

int_temp = TypeClassTemp('int')
float_temp = TypeClassTemp('float')
complex_temp = TypeClassTemp('complex')
str_temp = TypeClassTemp('str')
bool_temp = TypeClassTemp('bool')
func_temp = TypeClassTemp('function')

ellipsis_type = ellipsis_temp.get_default_type()
none_type = none_temp.get_default_type()
any_type = any_temp.get_default_type()

any_ins = any_type.call()
ellipsis_ins = ellipsis_type.call()

# dummy, used for test
dummy_temp = TypeDummyTemp()

# defer related

DeferBindEle = Union['Deferred', List['Deferred']]


class DeferredBindList:
    def __init__(self) -> None:
        self.binding: List[DeferBindEle] = []

    def add_binded(self, binded: Union['DeferredElement',
                                       DeferBindEle]) -> None:
        if isinstance(binded, DeferredElement):
            defer = Deferred()
            defer.add_element(binded)
            self.binding.append(defer)
            return
        assert isinstance(binded, (Deferred, list))
        self.binding.append(binded)

    def get_bind(self, index: int) -> Union['Deferred', List['Deferred']]:
        return self.binding[index]

    def get_bind_cnt(self) -> int:
        return len(self.binding)


class DeferredElement:
    def __init__(self, name: str, bindlist: 'DeferredBindList'):
        self.name = name
        self.bindlist = bindlist

    def get_bind(self, index: int) -> DeferBindEle:
        return self.bindlist.get_bind(index)

    def get_bind_cnt(self) -> int:
        return self.bindlist.get_bind_cnt()


class Deferred:
    def __init__(self) -> None:
        self.elements: List[DeferredElement] = []

    def add_element(self, item: DeferredElement):
        assert isinstance(item, DeferredElement)
        self.elements.append(item)

    def get(self, index: int) -> DeferredElement:
        return self.elements[index]


EntryType = Union[TypeIns, Deferred]


class Entry:
    def __init__(self, tp: EntryType, defnode: Optional[ast.AST] = None):
        # TODO: turn defnode to non-optional
        self.tp = tp
        self.defnode = defnode

    def get_type(self) -> TypeIns:
        if isinstance(self.tp, Deferred):
            return any_ins
        else:
            return self.tp

    def get_real_type(self) -> EntryType:
        return self.tp

    def set_type(self, entry_tp: EntryType):
        self.tp = entry_tp


# helper functions
def get_entry_type_name(entry_tp: EntryType) -> str:
    if isinstance(entry_tp, Deferred):
        return entry_tp.get(0).name
    else:
        return entry_tp.name
