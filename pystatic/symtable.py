import ast
import enum
from pystatic.symid import SymId, symid2list
from typing import (Dict, Optional, Union, List, TYPE_CHECKING, Tuple)
from pystatic.option import Option
from pystatic.errorcode import *

if TYPE_CHECKING:
    from pystatic.typesys import TypeIns, TypeTemp, TypeClassTemp
    from pystatic.predefined import TypeFuncIns


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

    def get_type(self, symtb: 'SymTable') -> 'TypeIns':
        return self._tp

    def get_defnode(self) -> Optional[ast.AST]:
        return self._defnode


class ImportEntry(Entry):
    def __init__(self,
                 module_symid: 'SymId',
                 origin_name: 'SymId',
                 defnode: Optional[ast.AST] = None) -> None:
        self._module_symid = module_symid
        self._origin_name = origin_name
        self._defnode = defnode

    def get_type(self, symtb: 'SymTable'):
        return symtb.import_cache.lookup_cache(self._module_symid,
                                               self._origin_name)


class ImportCache:
    __slots__ = ['import_nodes', 'import_map', '_cache']

    def __init__(self) -> None:
        self.import_nodes: List['ImportNode'] = []
        self.import_map: Dict[str, 'TypeIns'] = {}

        self._cache: Dict[SymId, Dict[SymId, 'TypeIns']] = {}

    def get_moduleins(self, abssymid: 'SymId') -> Optional['TypeIns']:
        from pystatic.predefined import TypePackageIns, TypeModuleTemp

        symidlist = symid2list(abssymid)
        if not symidlist:
            return None
        cur_ins = self.import_map.get(symidlist[0], None)

        for i in range(1, len(symidlist)):
            if not cur_ins:
                return None

            if isinstance(cur_ins, TypePackageIns):
                cur_ins = cur_ins.submodule.get(symidlist[i], None)
            else:
                assert isinstance(cur_ins.temp, TypeModuleTemp)
                if i == len(symidlist) - 1:
                    return cur_ins
                else:
                    return None

        return cur_ins

    def set_moduleins(self, abssymid: 'SymId', modins: 'TypeIns'):
        self.import_map[abssymid] = modins

    def add_import_node(self, node: 'ImportNode'):
        self.import_nodes.append(node)

    def add_cache(self, module_symid: str, origin_name: str, ins: 'TypeIns'):
        module_map = self._cache.setdefault(module_symid, {})
        module_map[origin_name] = ins

    def lookup_cache(self, module_symid: str,
                     origin_name: str) -> Optional['TypeIns']:
        module_map = self._cache.get(module_symid)
        if not module_map:
            return None
        else:
            return module_map.get(origin_name)


class SymTable:
    def __init__(self, symid: 'SymId', glob: 'SymTable',
                 non_local: Optional['SymTable'], builtins: 'SymTable',
                 scope: 'TableScope') -> None:
        self.symid = symid

        self.local: Dict[str, Entry] = {}
        self.non_local = non_local
        self.glob = glob
        self.builtins = builtins

        self.scope = scope

        self.import_cache = ImportCache()

        # inner data structure to store important information about this
        # symtable, used heavily in the preprocess stage.
        self._cls_defs: Dict[str, 'TypeClassTemp'] = {}
        self._spt_types: Dict[str, 'TypeTemp'] = {}  # special type template
        self._func_defs: Dict[str, 'TypeFuncIns'] = {}

    @property
    def glob_symid(self):
        return self.glob.symid

    def _legb_lookup(self, name: str, find):
        curtable: Optional[SymTable] = self
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

    def add_type_def(self, name: str, temp: 'TypeClassTemp'):
        self._cls_defs[name] = temp

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
        return res.get_type(self)

    def lookup(self, name: str) -> Optional['TypeIns']:
        return self._legb_lookup(name, SymTable.lookup_local)

    def getattr(self, name: str) -> Optional['TypeIns']:
        return self.lookup(name)

    def getattribute(self, name: str, node: ast.AST) -> Option['TypeIns']:
        """Getattribute from symtable

        support the getattribute interface.
        """
        from pystatic.typesys import any_ins  # avoid import circle
        res_option = Option(any_ins)
        res = self.lookup(name)
        if not res:
            res_option.add_err(SymbolUndefined(node, name))
        else:
            res_option.set_value(res)
        return res_option

    def add_entry(self, name: str, entry: Entry):
        self.local[name] = entry

    def new_symtable(self, name: str, new_scope: 'TableScope') -> 'SymTable':
        builtins = self.builtins
        if self.scope == TableScope.CLASS:
            non_local = self.non_local
        else:
            non_local = self
        glob = self.glob
        new_symid = self.symid + '.' + name
        return SymTable(new_symid, glob, non_local, builtins, new_scope)

    def legb_lookup(self, name):
        return self._legb_lookup(name, SymTable.lookup_local)
