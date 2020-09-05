from typing import Optional, Dict, List, Tuple, Union
from collections import OrderedDict
from pystatic.util import Uri, BindException

ARIBITRARY_ARITY = -1

TypeBind = Dict['TypeVar', 'TypeType']


class BaseType(object):
    def __init__(self, typename: str):
        self.name = typename

    @property
    def arity(self):
        return 0

    @property
    def basename(self) -> str:
        rpos = self.name.rfind('.')
        return self.name[rpos + 1:]

    def has_method(self, name: str) -> bool:
        return False

    def has_attribute(self, name: str) -> bool:
        return False

    def __str__(self):
        """ Used for type hint """
        return self.name

    def __contains__(self, name):
        return self.has_method(name) or self.has_attribute(name)


class TypeTemp(BaseType):
    def __init__(self, name):
        super().__init__(name)

    def _bind_types(self, bindlist: List['TypeType']) -> TypeBind:
        if len(bindlist) == 0:
            return {}
        raise BindException([], f"No binding is allowed in {self.basename}")

    def getattr(self, name: str) -> Optional['TypeIns']:
        """get attribute's type"""
        return None

    def get_type(self,
                 bindlist: List['TypeType'],
                 binded: Optional[TypeBind] = None) -> 'TypeType':
        """May throw BindException

        Usually you should make sure when binded and bindlist both are empty then
        it will not fail"""
        new_bind = self._bind_types(bindlist)
        old_bind = binded or {}
        return TypeType(self, dict(old_bind, **new_bind))


class TypeIns(BaseType):
    def __init__(self, temp: TypeTemp, binds: TypeBind):
        super().__init__(temp.name)
        self.temp = temp
        self.binds = binds

    def set_params(self, params: List['TypeType']):
        self.params = params

    def has_attribute(self, name: str) -> bool:
        return self.temp.has_attribute(name)

    def has_method(self, name: str) -> bool:
        return self.temp.has_method(name)

    def getattr(self, name: str) -> Optional['TypeIns']:
        return self.temp.getattr(name)


class TypeType(TypeIns):
    def __init__(self, temp: TypeTemp, binds: TypeBind):
        super().__init__(temp, binds)

    def getitem(
        self, tp_args: Union['TypeType', Tuple['TypeType']]
    ) -> Optional['TypeType']:
        """getitem of typetype returns a new typetype with new bindings"""
        if isinstance(tp_args, tuple):
            bindlist = list(tp_args)
        else:
            bindlist = [tp_args]
        return self.temp.get_type(bindlist, self.binds)


class TypeTypeClass(TypeType):
    def __init__(self, temp: 'TypeClassTemp', binds: TypeBind):
        super().__init__(temp, binds)


class TypeVar(TypeTemp):
    def __init__(self,
                 name: str,
                 *args: TypeIns,
                 bound: Optional[BaseType] = None,
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
        self.constrains: List[TypeIns] = list(*args)


class TypeClassTemp(TypeTemp):
    def __init__(self, clsname: str):
        super().__init__(clsname)
        self.baseclass: Dict[str, TypeClass] = OrderedDict()

        self.method: dict = {}
        self.cls_attr: Dict[str, TypeIns] = {}
        self.var_attr: Dict[str, TypeIns] = {}

        self.typevar: Dict[str, TypeVar] = OrderedDict()

    def add_inner_type(self, name: str, tp: 'TypeTemp'):
        if tp.basename in self.cls_attr:
            #TODO: warning here
            return None
        self.cls_attr[tp.basename] = tp.get_type([])

    def set_typevar(self, typevar: OrderedDict):
        self.typevar = typevar

    def add_base(self, basename: str, base_type):
        self.baseclass[basename] = base_type

    def add_method(self, name: str, method_type):
        self.method[name] = method_type

    def has_method(self, name: str) -> bool:
        if not (name in self.method):
            for v in self.baseclass.values():
                if v.has_method(name):
                    return True
            return False
        return True

    def add_var_attr(self, name: str, attr_type: TypeIns):
        self.var_attr[name] = attr_type

    def add_cls_attr(self, name: str, attr_type: TypeIns):
        self.cls_attr[name] = attr_type

    def add_attribute(self, name: str, attr_type: TypeIns):
        """Same as add_var_attr"""
        self.add_var_attr(name, attr_type)

    def has_attribute(self, name: str) -> bool:
        if name in self.var_attr or name in self.cls_attr:
            return True
        else:
            for v in self.baseclass.values():
                if v.has_attribute(name):
                    return True
            return False

    def getattr(self, name: str) -> Optional['TypeIns']:
        if name in self.var_attr:
            return self.var_attr[name]
        elif name in self.cls_attr:
            return self.cls_attr[name]
        else:
            for base in self.baseclass.values():
                res = base.getattr(name)
                if res:
                    return res
            return None

    def bind_types(self, bind: List['TypeType']) -> TypeBind:
        if len(bind) == 0:
            # default is all Any
            bind = [any_type for i in range(len(self.typevar))]

        if len(bind) != len(self.typevar):
            raise BindException(
                [], f"get {len(bind)} arguments, require {len(self.typevar)}")
        res = {}
        for tpvar, bind_type in zip(self.typevar, bind):
            # TODO: check consistence
            res[tpvar] = bind_type
        return res

    def get_type(self,
                 bind: List['TypeType'],
                 binded: Optional[TypeBind] = None) -> 'TypeTypeClass':
        new_bind = self.bind_types(bind)
        old_bind = binded or {}
        return TypeTypeClass(self, dict(old_bind, **new_bind))


class TypeClass(TypeIns):
    def __init__(self, temp: TypeClassTemp, *args):
        super().__init__(temp, *args)


class TypeModuleTemp(TypeClassTemp):
    def __init__(self, uri: Uri, types: Dict[str, TypeTemp],
                 local: Dict[str, TypeIns]):
        super().__init__(uri)
        for tpname in types.keys():
            tpres = types[tpname].get_type([])
            assert tpres
            if tpres:
                self.cls_attr[tpname] = tpres
        self.cls_attr.update(local)

    @property
    def uri(self):
        return self.name


class TypePackageTemp(TypeModuleTemp):
    def __init__(self, paths: List[str], uri: Uri, tp: Dict[str, TypeTemp],
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


class TypeCallableTemp(TypeTemp):
    def __init__(self):
        super().__init__('Callable')


class TypeGenericTemp(TypeTemp):
    def __init__(self):
        super().__init__('Generic')


class TypeFunc(TypeClass):
    def __init__(self, arg, ret_type: BaseType):
        super().__init__(func_temp)
        self.arg = arg
        self.ret_type = ret_type

    def __str__(self):
        return str(self.arg) + ' -> ' + str(self.ret_type)


class EllipsisIns(TypeClass):
    def __init__(self) -> None:
        super().__init__(ellipsis_temp)

    def __str__(self):
        return '...'


# default types
any_temp = TypeAnyTemp()
none_temp = TypeNoneTemp()
generic_temp = TypeGenericTemp()

int_temp = TypeClassTemp('int')
float_temp = TypeClassTemp('float')
complex_temp = TypeClassTemp('complex')
str_temp = TypeClassTemp('str')
bool_temp = TypeClassTemp('bool')
func_temp = TypeClassTemp('function')
ellipsis_temp = TypeClassTemp('ellipsis')

ellipsis_type = ellipsis_temp.get_type([])
none_type = none_temp.get_type([])
any_type = any_temp.get_type([])
