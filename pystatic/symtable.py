import ast
import enum
from typing import (Dict, Optional, Union, List, TYPE_CHECKING, Tuple)
from pystatic.option import Option
from pystatic.errorcode import *

if TYPE_CHECKING:
    from pystatic.typesys import (TypeIns, TypeClassTemp, TypeTemp,
                                  TypeFuncIns)
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

    def get_type(self) -> 'TypeIns':
        return self._tp

    def get_defnode(self) -> Optional[ast.AST]:
        return self._defnode

    def __str__(self):
        return str(self._tp)

class SymTable:
    def __init__(self, uri: 'Uri', glob: 'SymTable',
                 non_local: Optional['SymTable'], builtins: 'SymTable',
                 scope: 'TableScope') -> None:
        self.uri = uri

        self.local: Dict[str, Entry] = {}
        self.non_local = non_local
        self.glob = glob
        self.builtins = builtins

        self.scope = scope

        # inner data structure to store important information about this
        # symtable, used heavily in the preprocess stage.
        self._cls_defs: Dict[str, 'TypeClassTemp'] = {}
        self._spt_types: Dict[str, 'TypeTemp'] = {}  # special type template
        self._func_defs: Dict[str, 'TypeFuncIns'] = {}

        self._import_nodes: List[ImportNode] = []
        self._import_tree: Dict[str, 'TypeIns'] = {}

    @property
    def glob_uri(self):
        return self.glob.uri

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

    def getattribute(self, name: str, node: ast.AST) -> Option['TypeIns']:
        """Getattribute from symtable

        support the getattribute interface.
        """
        from pystatic.typesys import any_ins  # avoid import circle
        option_res = Option(any_ins)
        res = self.lookup(name)
        if not res:
            option_res.add_err(SymbolUndefined(node, name))
        else:
            option_res.set_value(res)
        return option_res

    def lookup_local_entry(self, name: str) -> Optional['Entry']:
        return self.local.get(name)

    def lookup_entry(self, name: str) -> Optional['Entry']:
        return self._legb_lookup(name, SymTable.lookup_local_entry)

    def add_entry(self, name: str, entry: Entry):
        self.local[name] = entry

    def new_symtable(self, name: str, new_scope: 'TableScope') -> 'SymTable':
        builtins = self.builtins
        if self.scope == TableScope.CLASS:
            non_local = self.non_local
        else:
            non_local = self
        glob = self.glob
        new_uri = self.uri + '.' + name
        return SymTable(new_uri, glob, non_local, builtins, new_scope)

    def legb_lookup(self, name):
        return self._legb_lookup(name, SymTable.lookup_local)
