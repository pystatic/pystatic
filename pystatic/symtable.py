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
ImportNode = Union[ast.Import, ast.ImportFrom]
ImportItem = Tuple[AsName, OriginName, ImportNode]

TypeDefNode = Union[str, ast.AST]


class Entry:
    def __init__(self, tp: 'TypeIns', defnode: Optional[ast.AST] = None):
        self._tp = tp
        self._defnode = defnode

    def set_type(self, tp: 'TypeIns'):
        self._tp = tp

    def get_type(self) -> 'TypeIns':
        return self._tp

    def set_defnode(self, defnode: ast.AST):
        self._defnode = defnode

    def get_defnode(self) -> Optional[ast.AST]:
        return self._defnode


class SymTable:
    def __init__(self, glob: 'SymTable', non_local: Optional['SymTable'],
                 builtins: 'SymTable', scope: 'TableScope') -> None:
        self.local: Dict[str, Entry] = {}
        self.non_local = non_local
        self.glob = glob
        self.builtins = builtins

        self.scope = scope

        self._cls_defs: Dict[str, 'TypeClassTemp'] = OrderedDict()
        self._spt_types: Dict[str, 'TypeTemp'] = {}  # special type template

        self._import_info: Dict['Uri', List[ImportItem]] = {}

        self._functions = set()

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
        if curtable:
            res = find(curtable, name)
        if res:
            return res
        return find(self.builtins, name)

    def get_type_def(self, name: str) -> Optional['TypeTemp']:
        findlist = name.split('.')
        assert findlist
        if name in self._cls_defs:
            cur_temp = self._cls_defs[name]
        elif name in self._spt_types:
            cur_temp = self._spt_types[name]
        else:
            return None

        lenf = len(findlist)
        for i in range(1, lenf):
            if cur_temp:
                cur_temp = cur_temp.get_inner_typedef(findlist[i])
            else:
                return None
        return cur_temp

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

    def new_symtable(self, new_scope: 'TableScope') -> 'SymTable':
        builtins = self.builtins
        if self.scope == TableScope.CLASS:
            non_local = self.non_local
        else:
            non_local = self
        glob = self.glob
        return SymTable(glob, non_local, builtins, new_scope)
