import os
from typing import Optional, Dict, List, Union, TYPE_CHECKING
from collections import OrderedDict

ARIBITRARY_ARITY = -1

if TYPE_CHECKING:
    from pystatic.manager import Manager


class BaseType(object):
    def __init__(self, typename: str):
        self.name = typename

    @property
    def arity(self):
        return 0

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

    @property
    def arity(self):
        return self._arity

    @arity.setter
    def arity(self, x: int):
        self._arity = x

    def instantiate(self, bind: List[BaseType]) -> 'TypeIns':
        return TypeIns(self, *bind)


class TypeIns(BaseType):
    def __init__(self, temp: TypeTemp, *args: BaseType):
        super().__init__(temp.name)
        self.temp = temp
        self.param = list(args)

    @property
    def template(self):
        return self.temp


class TypeVar(TypeTemp):
    def __init__(self,
                 name: str,
                 *args,
                 bound: Optional[BaseType] = None,
                 covariant=False,
                 contravariant=False):
        super().__init__(name)
        self.bound = bound
        if contravariant:
            self.convariant = False
        else:
            self.convariant = covariant
        if contravariant or covariant:
            self.invariant = False
        else:
            self.invariant = True
        self.contravariant = contravariant


class TypeClassTemp(TypeTemp):
    def __init__(self, clsname: str):
        super().__init__(clsname)
        self.baseclass = OrderedDict()
        self.method = {}
        self.attribute: Dict[str, TypeIns] = {}

        self.typevar = OrderedDict()

        self.inner_type: Dict[str, TypeTemp] = {}

    def instantiate(self, bind: List[BaseType]):
        return TypeClass(self, *bind)

    def add_type(self, name: str, tp: TypeTemp):
        self.inner_type[name] = tp

    def get_type(self, name: str) -> Optional[TypeTemp]:
        res = self.inner_type.get(name)
        if not res:
            for v in self.baseclass.values():
                res = v.template.get_type(name)
                if res:
                    return res
        return res

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

    def add_attribute(self, name: str, attr_type: TypeIns):
        self.attribute[name] = attr_type

    def has_attribute(self, name: str) -> bool:
        if not (name in self.attribute):
            for v in self.baseclass.values():
                if v.has_attribute(name):
                    return True
            return False
        return True


class TypeModuleTemp(TypeClassTemp):
    def __init__(self, path: str, uri: str, tp: Dict[str, TypeTemp],
                 local: Dict[str, TypeIns]):
        super().__init__('module')
        self.inner_type = tp
        self.attribute = local
        self.path = path
        self.uri = uri


class TypePackageTemp(TypeClassTemp):
    def __init__(self, path: List[str], uri: str, manager: 'Manager'):
        super().__init__('package')
        self.path = path
        self.uri = uri
        self.manager = manager

    def get_type(self, imp: str) -> Optional[TypeTemp]:
        return self.manager.deal_import(imp, self)


class TypeAny(TypeTemp):
    def __init__(self):
        super().__init__('Any', 0)

    def has_method(self, name: str) -> bool:
        return True

    def has_attribute(self, name: str) -> bool:
        return True


class TypeNone(TypeTemp):
    def __init__(self):
        super().__init__('None', 0)

    def has_method(self, name: str) -> bool:
        return False

    def has_attribute(self, name: str) -> bool:
        return False


class TypeTuple(TypeTemp):
    def __init__(self):
        super().__init__('Tuple', ARIBITRARY_ARITY)


class TypeDict(TypeTemp):
    def __init__(self):
        super().__init__('Dict', 2)


class TypeUnion(TypeTemp):
    def __init__(self):
        super().__init__('Union', ARIBITRARY_ARITY)


class TypeOptional(TypeTemp):
    def __init__(self):
        super().__init__('Optional', 1)


class TypeCallable(TypeTemp):
    def __init__(self):
        super().__init__('Callable', 2)


class TypeGeneric(TypeTemp):
    def __init__(self):
        super().__init__('Generic', ARIBITRARY_ARITY)


class TypeClass(TypeIns):
    def __init__(self, temp: TypeClassTemp, *args):
        super().__init__(temp, *args)

    def has_attribute(self, name: str) -> bool:
        return self.temp.has_attribute(name)

    def has_method(self, name: str) -> bool:
        return self.temp.has_method(name)


class TypeFunc(TypeClass):
    def __init__(self, arg, ret_type: BaseType):
        super().__init__(func_type)
        self.arg = arg
        self.ret_type = ret_type

    def __str__(self):
        return str(self.arg) + ' -> ' + str(self.ret_type)


ImpItem = Union[TypeModuleTemp, TypePackageTemp]

# default types
any_type = TypeAny()
none_type = TypeNone()
generic_type = TypeGeneric()

int_type = TypeClassTemp('int')
float_type = TypeClassTemp('float')
complex_type = TypeClassTemp('complex')
str_type = TypeClassTemp('str')
bool_type = TypeClassTemp('bool')
func_type = TypeClassTemp('function')
