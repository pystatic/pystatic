import ast
import enum
from typing import (Dict, Optional, Union, List, Set)
from pystatic.typesys import TypeIns, any_ins, TypeClassTemp, Entry


class Tabletype(enum.Enum):
    GLOB = 1
    CLASS = 2
    FUNC = 3


class SymTable:
    """Symbol table"""
    def __init__(self, glob: 'SymTable', non_local: Optional['SymTable'],
                 builtins: 'SymTable', table_type: 'Tabletype') -> None:
        self.local: Dict[str, Entry] = {}
        self.non_local = non_local
        self.glob = glob
        self.builtins = builtins

        self.anonymous_entry: Set[Entry] = set()

        self.table_type = table_type

        self.subtables = set()

        self.attach: Optional[TypeClassTemp] = None

    def set_attach(self, tp_temp: 'TypeClassTemp'):
        self.attach = tp_temp

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
        if self.attach and self.table_type == Tabletype.CLASS:
            self.attach.add_clsvar(name, entry)

    def add_anon_entry(self, entry: 'Entry'):
        """Add anonymous entry(mainly used for remove defer)"""
        self.anonymous_entry.add(entry)

    def add_subtable(self, symtable: 'SymTable'):
        assert symtable.table_type != Tabletype.GLOB
        self.subtables.add(symtable)
