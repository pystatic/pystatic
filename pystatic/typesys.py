from optparse import Option
from typing import Optional, Dict, List, Tuple, Union
from collections import OrderedDict
from pystatic.moduri import ModUri
from pystatic.util import BindException, BindError

TypeBind = Dict['TypeVar', 'TypeType']
TypeList = List['TypeVar']
BindList = List['TypeType']


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
    def __init__(self, name, typelist: TypeList):
        super().__init__(name)
        self.typelist = typelist

    def set_typelist(self, typelist: TypeList):
        self.typelist = typelist

    def _bind_types(self, bindlist: BindList) -> TypeBind:
        if len(bindlist) == 0:
            return {}
        raise BindException([], f"No binding is allowed in {self.basename}")

    def get_type(self,
                 bindlist: BindList,
                 binded: Optional[TypeBind] = None) -> 'TypeType':
        """Usually you should make sure when binded and bindlist both are empty
        then it will not fail.

        May throw BindException."""
        new_bind = self._bind_types(bindlist)
        old_bind = binded or {}
        return TypeType(self, {**old_bind, **new_bind})

    def get_default_type(self,
                         binded: Optional[TypeBind] = None) -> 'TypeType':
        try:
            return self.get_type([], binded)
        except BindException as e:
            assert 0, "Default type should always succeed"
            raise e

    def setattr(self, name: str, attr_type: 'TypeIns'):
        pass

    def getattr(self,
                name: str,
                binds: Optional[TypeBind] = None) -> Optional['TypeIns']:
        """get attribute's type"""
        return None


class TypeIns(BaseType):
    def __init__(self, temp: TypeTemp, binds: TypeBind):
        super().__init__(temp.name)
        self.temp = temp
        self.binds = binds

    def substitute(self, outer_binds: Optional[TypeBind] = None) -> TypeBind:
        outer_binds = outer_binds or {}
        return {**outer_binds, **self.binds}

    def getattr(self,
                name: str,
                outer_binds: Optional[TypeBind] = None) -> Optional['TypeIns']:
        return self.temp.getattr(name, self.substitute(outer_binds))

    def __str__(self) -> str:
        bindlist = list(self.binds.values())
        if bindlist:
            tplist_str = ', '.join(map(lambda tp: tp.basename, bindlist))
            return self.name + '[' + tplist_str + ']'
        else:
            return self.name


class TypeType(TypeIns):
    def __init__(self, temp: TypeTemp, binds: TypeBind):
        super().__init__(temp, binds)

    def call(self) -> 'TypeIns':
        return TypeIns(self.temp, self.binds)

    def getitem(self, bindlist: BindList) -> Optional['TypeType']:
        """getitem of typetype returns a new typetype with new bindings

        May throw BindException
        """
        return self.temp.get_type(bindlist, self.binds)


class TypeVar(TypeTemp):
    def __init__(self,
                 name: str,
                 *args: TypeIns,
                 bound: Optional[BaseType] = None,
                 covariant=False,
                 contravariant=False):
        super().__init__(name, [])
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
        super().__init__(clsname, [])

        self.baseclass: 'OrderedDict[str, TypeType]'
        self.baseclass = OrderedDict()

        self.method: dict = {}
        self.cls_attr: Dict[str, TypeIns] = {}
        self.var_attr: Dict[str, TypeIns] = {}

    def _bind_types(self, bindlist: BindList) -> TypeBind:
        binds: TypeBind = {}
        if not bindlist:
            return binds  # TODO: this may be wrong
        else:
            if len(bindlist) != len(self.typelist):
                raise BindException(
                    [],
                    f'{self.basename} require {len(self.typelist)} but {len(bindlist)} given'
                )
            else:
                for tpvar, tpbind in zip(self.typelist, bindlist):
                    binds[tpvar] = tpbind
                return binds

    def add_base(self, base_type: TypeType):
        self.baseclass[base_type.name] = base_type

    def add_method(self, name: str, method_type):
        self.method[name] = method_type

    def add_var_attr(self, name: str, attr_type: TypeIns):
        self.var_attr[name] = attr_type

    def add_cls_attr(self, name: str, attr_type: TypeIns):
        self.cls_attr[name] = attr_type

    def get_local_attr(
            self,
            name: str,
            binds: Optional[TypeBind] = None) -> Optional['TypeIns']:
        if name in self.var_attr:
            return self.var_attr[name]
        elif name in self.cls_attr:
            return self.cls_attr[name]
        return None

    def setattr(self, name: str, attr_type: 'TypeIns'):
        """Same as add_cls_attr"""
        self.add_cls_attr(name, attr_type)

    def getattr(self,
                name: str,
                binds: Optional[TypeBind] = None) -> Optional['TypeIns']:
        local_res = self.get_local_attr(name, binds)
        if local_res:
            return local_res
        else:
            for basecls in self.baseclass.values():
                res = basecls.getattr(name, binds)
                if res:
                    return res
            return None


class TypeModuleTemp(TypeClassTemp):
    def __init__(self, uri: ModUri, types: Dict[str, TypeTemp],
                 local: Dict[str, TypeIns]):
        super().__init__(uri)
        for tpname in types.keys():
            tpres = types[tpname].get_default_type()
            assert tpres
            if tpres:
                self.cls_attr[tpname] = tpres
        self.cls_attr.update(local)

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
        super().__init__('Any', [])

    def has_method(self, name: str) -> bool:
        return True

    def has_attribute(self, name: str) -> bool:
        return True


class TypeNoneTemp(TypeTemp):
    def __init__(self):
        super().__init__('None', [])

    def has_method(self, name: str) -> bool:
        return False

    def has_attribute(self, name: str) -> bool:
        return False


class TypeTupleTemp(TypeTemp):
    def __init__(self):
        super().__init__('Tuple', [])


class TypeDictTemp(TypeTemp):
    def __init__(self):
        super().__init__('Dict', [])


class TypeUnionTemp(TypeTemp):
    def __init__(self):
        super().__init__('Union', [])


class TypeOptionalTemp(TypeTemp):
    def __init__(self):
        super().__init__('Optional', [])


class TypeCallableTemp(TypeTemp):
    def __init__(self):
        super().__init__('Callable', [])


class TypeGenericTemp(TypeTemp):
    def __init__(self):
        super().__init__('Generic', [])

    def _bind_types(self, bindlist: BindList) -> TypeBind:
        res: TypeBind = {}
        errors: BindError = []
        for i, binditem in enumerate(bindlist):
            if not isinstance(binditem.temp, TypeVar):
                errors.append((i, f'{binditem.basename} is not a TypeVar'))
            else:
                res[binditem.temp] = binditem
        if errors:
            raise BindException(errors, '')
        return res


class TypeFuncIns(TypeIns):
    def __init__(self, arg, ret_type: BaseType):
        super().__init__(func_temp, {})
        self.arg = arg
        self.ret_type = ret_type

    def __str__(self):
        return str(self.arg) + ' -> ' + str(self.ret_type)


class EllipsisIns(TypeIns):
    def __init__(self) -> None:
        super().__init__(ellipsis_temp, {})

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

ellipsis_type = ellipsis_temp.get_default_type()
none_type = none_temp.get_default_type()
any_type = any_temp.get_default_type()

any_ins = any_type.call()
ellipsis_ins = ellipsis_type.call()


# helper functions
def bind(tp_type: TypeType, bindlist: BindList) -> TypeType:
    pass
