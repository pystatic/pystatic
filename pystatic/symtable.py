import ast
import enum
from collections import OrderedDict
from typing import (Dict, Optional, Union, List, TYPE_CHECKING, Tuple)

if TYPE_CHECKING:
    from pystatic.typesys import TypeIns, TypeClassTemp, TypeTemp
    from pystatic.uri import Uri


class TableScope(enum.Enum):
    GLOB = 1
    CLASS = 2
    FUNC = 3


AsName = str
OriginName = str
ImportItem = Tuple[AsName, OriginName]  # (moduri, name)
EntryType = Optional['TypeIns']

TypeDefNode = Union[str, ast.AST]


class Entry:
    def __init__(self,
                 tp: EntryType,
                 defnode: Optional[ast.AST] = None,
                 tpnode: Optional[TypeDefNode] = None):
        self._tp = tp
        self._defnode = defnode
        self._typenode = tpnode

    def set_type(self, tp: EntryType):
        self._tp = tp

    def get_type(self) -> EntryType:
        return self._tp

    def set_defnode(self, defnode: ast.AST):
        self._defnode = defnode

    def get_defnode(self) -> Optional[ast.AST]:
        return self._defnode

    def set_typenode(self, tpnode: ast.AST):
        self._typenode = tpnode

    def get_typenode(self) -> Optional[TypeDefNode]:
        return self._typenode or self._defnode


class SymTable:
    def __init__(self, glob: 'SymTable', non_local: Optional['SymTable'],
                 builtins: 'SymTable', scope: 'TableScope') -> None:
        self.local: Dict[str, Entry] = {}
        self.non_local = non_local
        self.glob = glob
        self.builtins = builtins

        self._scope = scope

        self.cls_defs: Dict[str, 'TypeClassTemp'] = OrderedDict()
        self.spt_defs: Dict[str, 'TypeTemp'] = {}  # special type template

        self.import_info: Dict['Uri', List[ImportItem]] = {}

        self.functions = set()

    def add_cls_def(self, name: str, temp: 'TypeClassTemp'):
        self.cls_defs[name] = temp

    def add_spt_def(self, name: str, temp: 'TypeTemp'):
        self.spt_defs[name] = temp

    def get_type_def(self, name: str) -> Optional['TypeTemp']:
        findlist = name.split('.')
        assert findlist
        if name in self.cls_defs:
            cur_temp = self.cls_defs[name]
        elif name in self.spt_defs:
            cur_temp = self.spt_defs[name]
        else:
            return None

        lenf = len(findlist)
        for i in range(1, lenf):
            if cur_temp:
                cur_temp = cur_temp.get_inner_typedef(findlist[i])
            else:
                return None
        return cur_temp

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
        return res.get_type()

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

    def add_fun_entry(self, name: str, entry: Entry):
        self.functions.add(name)
        self.local[name] = entry

    def add_import_item(self, name: str, uri: 'Uri', origin_name: str,
                        defnode: ast.AST):
        """Add import information to the symtable"""
        self.local[name] = Entry(None, defnode)  # TODO: name collision?
        self.import_info.setdefault(uri, []).append((name, origin_name))

    def new_symtable(self, new_scope: 'TableScope') -> 'SymTable':
        builtins = self.builtins
        if self._scope == TableScope.CLASS:
            non_local = self.non_local
        else:
            non_local = self
        glob = self.glob
        return SymTable(glob, non_local, builtins, new_scope)
