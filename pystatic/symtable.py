import ast
import enum
from typing import (Dict, Optional, Union, List)
from pystatic.typesys import TypeIns, any_ins


class Tabletype(enum.Enum):
    GLOB = 1
    CLASS = 2
    FUNC = 3


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
    name = 'Deferred'  # make EntryType has attribute: name

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


class SymTable:
    """Symbol table"""
    def __init__(self, glob: 'SymTable', non_local: Optional['SymTable'],
                 builtins: 'SymTable', table_type: 'Tabletype') -> None:
        self.local: Dict[str, Entry] = {}
        self.non_local = non_local
        self.glob = glob
        self.builtins = builtins

        self.table_type = table_type

        self.defer = set()

    def _legb_lookup(self, name: str, find):
        curtable = self
        res = find(curtable, name)
        if res:
            return res
        curtable = self.non_local
        while curtable:
            res = find(curtable, name)
            if res:
                return res
            curtable = curtable.non_local
        curtable = self.glob
        res = find(curtable, name)
        if res:
            return res
        return find(self.builtins, name)

    def lookup_local(self, name: str) -> Optional['TypeIns']:
        res = self.local.get(name)
        if not res:
            return None
        res = res.tp
        if not isinstance(res, TypeIns):  # Deferred
            return any_ins
        return res

    def lookup(self, name: str) -> Optional['TypeIns']:
        return self._legb_lookup(name, SymTable.lookup_local)

    def getattr(self, name: str) -> Optional['TypeIns']:
        return self.lookup(name)

    def lookup_local_entry(self, name: str) -> Optional['Entry']:
        return self.local.get(name)

    def lookup_entry(self, name: str) -> Optional['Entry']:
        return self._legb_lookup(name, SymTable.lookup_local_entry)

    def add_entry(self, name: str, entry: Entry):
        self.local[name] = entry
