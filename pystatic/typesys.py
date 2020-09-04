from typing import Optional, Dict, List, Tuple, Union
from collections import OrderedDict
from pystatic.util import Uri

ARIBITRARY_ARITY = -1


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
    def __init__(self, name, arity=0):
        super().__init__(name)
        self._arity = arity
        self._type = TypeType(self, [])

    @property
    def arity(self):
        return self._arity

    @arity.setter
    def arity(self, x: int):
        self._arity = x

    def instantiate(self, bind: List['TypeType']) -> 'TypeIns':
        return TypeIns(self, *bind)

    def getattr(self, name: str) -> Optional['TypeIns']:
        """get attribute's type"""
        return None

    def get_type(self) -> 'TypeType':
        return self._type


class TypeIns(BaseType):
    def __init__(self, temp: TypeTemp, *args: 'TypeType'):
        super().__init__(temp.name)
        self.temp = temp
        self.params = list(args)

    def set_params(self, params: List['TypeType']):
        self.params = params

    def has_attribute(self, name: str) -> bool:
        return self.temp.has_attribute(name)

    def has_method(self, name: str) -> bool:
        return self.temp.has_method(name)

    def getattr(self, name: str) -> Optional['TypeIns']:
        return self.temp.getattr(name)


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

        self._type: TypeTypeClass = TypeTypeClass(self)

    def instantiate(self, bind: List['TypeType']):
        return TypeClass(self, *bind)

    def add_inner_type(self, name: str, tp: 'TypeTemp'):
        if tp.basename in self.cls_attr:
            #TODO: warning here
            return None
        self.cls_attr[tp.basename] = tp._type

    def set_typevar(self, typevar: OrderedDict):
        self.arity = len(typevar)
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

    def get_type(self) -> 'TypeTypeClass':
        return self._type


class TypeClass(TypeIns):
    def __init__(self, temp: TypeClassTemp, *args):
        super().__init__(temp, *args)


class TypeType(TypeIns):
    def __init__(self, temp: TypeTemp, params: List['TypeType']):
        super().__init__(temp)
        self.params = params

    def getitem(self, params: Union['TypeType',
                                    Tuple['TypeType']]) -> 'TypeType':
        if isinstance(params, tuple):
            return TypeType(self.temp, list(params))
        else:
            assert isinstance(params, TypeType)
            return TypeType(self.temp, [params])

    def instantiate(self) -> TypeIns:
        return self.temp.instantiate(self.params)


class TypeTypeClass(TypeType):
    def __init__(self, temp: 'TypeClassTemp'):
        super().__init__(temp, [])


class TypeModuleTemp(TypeClassTemp):
    def __init__(self, uri: Uri, types: Dict[str, TypeTemp],
                 local: Dict[str, TypeIns]):
        super().__init__(uri)
        for tpname in types.keys():
            self.cls_attr[tpname] = types[tpname].get_type()
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
        super().__init__('Any', 0)

    def has_method(self, name: str) -> bool:
        return True

    def has_attribute(self, name: str) -> bool:
        return True


class TypeNoneTemp(TypeTemp):
    def __init__(self):
        super().__init__('None', 0)

    def has_method(self, name: str) -> bool:
        return False

    def has_attribute(self, name: str) -> bool:
        return False


class TypeTupleTemp(TypeTemp):
    def __init__(self):
        super().__init__('Tuple', ARIBITRARY_ARITY)


class TypeDictTemp(TypeTemp):
    def __init__(self):
        super().__init__('Dict', 2)


class TypeUnionTemp(TypeTemp):
    def __init__(self):
        super().__init__('Union', ARIBITRARY_ARITY)


class TypeOptionalTemp(TypeTemp):
    def __init__(self):
        super().__init__('Optional', 1)


class TypeCallableTemp(TypeTemp):
    def __init__(self):
        super().__init__('Callable', 2)


class TypeGenericTemp(TypeTemp):
    def __init__(self):
        super().__init__('Generic', ARIBITRARY_ARITY)


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

ellipsis_type = ellipsis_temp.get_type()
none_type = none_temp.get_type()
any_type = any_temp.get_type()
