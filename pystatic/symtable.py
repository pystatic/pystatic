import ast
import enum
from pystatic.symid import SymId, symid2list
from typing import Dict, Optional, Union, List, TYPE_CHECKING, Tuple
from pystatic.result import Result
from pystatic.errorcode import *

if TYPE_CHECKING:
    from pystatic.manager import Manager
    from pystatic.typesys import TypeIns, TypeTemp
    from pystatic.arg import Argument


class TableScope(enum.Enum):
    GLOB = 1
    CLASS = 2
    FUNC = 3


AsName = str
OriginName = str
ImportNode = Union[ast.Import, ast.ImportFrom]
ImportItem = Tuple[AsName, OriginName, ImportNode]


class Entry:
    __slots__ = ["tp", "defnode"]

    def __init__(self, tp: "TypeIns", defnode: Optional[ast.AST] = None):
        self.tp = tp
        self.defnode = defnode

    def get_type(self, symtable: "SymTable") -> "TypeIns":
        return self.tp

    def get_defnode(self) -> Optional[ast.AST]:
        return self.defnode


class ImportEntry(Entry):
    __slots__ = ["module_symid", "origin_name", "defnode"]

    def __init__(
        self,
        module_symid: "SymId",
        origin_name: "SymId",
        defnode: Optional[ast.AST] = None,
    ) -> None:
        self.module_symid = module_symid
        self.origin_name = origin_name
        self.defnode = defnode

    def get_type(self, symtable: "SymTable"):
        return symtable.import_cache.lookup_cache(self.module_symid, self.origin_name)


class ImportCache:
    __slots__ = ["import_nodes", "import_map", "_cache"]

    def __init__(self) -> None:
        self.import_nodes: List["ImportNode"] = []
        self.import_map: Dict[str, "TypeIns"] = {}

        self._cache: Dict[SymId, Dict[SymId, "TypeIns"]] = {}

    def get_module_ins(self, abssymid: "SymId") -> Optional["TypeIns"]:
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

    def set_moduleins(self, abssymid: "SymId", modins: "TypeIns"):
        self.import_map[abssymid] = modins

    def add_import_node(self, node: "ImportNode"):
        self.import_nodes.append(node)

    def add_cache(self, module_symid: str, origin_name: str, ins: "TypeIns"):
        module_map = self._cache.setdefault(module_symid, {})
        module_map[origin_name] = ins

    def lookup_cache(self, module_symid: str, origin_name: str) -> Optional["TypeIns"]:
        module_map = self._cache.get(module_symid)
        if not module_map:
            return None
        else:
            return module_map.get(origin_name)

    def clear(self):
        self.import_map = {}
        self.import_nodes = []
        self._cache = {}


class SymTable:
    def __init__(
        self,
        symid: "SymId",
        glob: "SymTable",
        non_local: Optional["SymTable"],
        builtins: "SymTable",
        manager: "Manager",
        scope: "TableScope",
    ) -> None:
        self.symid = symid

        self.local: Dict[str, Entry] = {}
        self.non_local = non_local
        self.glob = glob
        self.builtins = builtins

        self.scope = scope

        self.import_cache = ImportCache()

        self.manager = manager
        # modules star imported
        self.star_import: List[SymId] = []

        # inner data structure to store important information about this
        # symtable, used heavily in the preprocess stage.
        self._tp_def: Dict[str, "TypeTemp"] = {}

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

    def add_type_def(self, name: str, temp: "TypeTemp"):
        self._tp_def[name] = temp

    def add_entry(self, name: str, entry: Entry):
        self.local[name] = entry

    def get_type_def(self, name: str) -> Optional["TypeTemp"]:
        findlist = name.split(".")
        assert findlist
        if name in self._tp_def:
            cur_temp = self._tp_def[name]
        else:
            return None

        lenf = len(findlist)
        for i in range(1, lenf):
            if cur_temp:
                cur_temp = cur_temp.get_inner_typedef(findlist[i])
            else:
                return None
        return cur_temp

    def lookup_local(self, name: str, search_star_import=True) -> Optional["TypeIns"]:
        """
        @param search_star_import: whether search in the module fully imported
        """
        res = self.local.get(name)
        if search_star_import and not res:
            searched = set(self.glob_symid)
            for module_symid in self.star_import:
                if module_symid not in searched:
                    searched.add(module_symid)
                    module_ins = self.manager.get_module_ins(module_symid)
                    res = module_ins._inner_symtable.lookup_local(name, False)
                    if res:
                        return res
            return None
        if res:
            return res.get_type(self)
        return None

    def legb_lookup(self, name):
        return self._legb_lookup(name, SymTable.lookup_local)

    def egb_lookup(self, name: str):
        find = SymTable.lookup_local
        curtable = self.non_local
        while curtable:
            res = find(curtable, name)
            if res:
                return res
            curtable = curtable.non_local
        return find(self.builtins, name)

    def getattribute(self, name: str, node: ast.AST) -> Result["TypeIns"]:
        """Getattribute from symtable

        support the getattribute interface.
        """
        from pystatic.typesys import any_ins  # avoid import circle

        result = Result(any_ins)
        res = self.legb_lookup(name)
        if not res:
            result.add_err(SymbolUndefined(node, name))
        else:
            result.set_value(res)
        return result

    def new_symtable(
        self, name: str, new_scope: "TableScope", param: Optional["Argument"] = None
    ) -> "SymTable":
        builtins = self.builtins
        if self.scope == TableScope.CLASS:
            non_local = self.non_local
        else:
            non_local = self
        glob = self.glob
        new_symid = self.symid + "." + name
        if new_scope == TableScope.FUNC:
            return FunctionSymTable(
                new_symid, glob, non_local, builtins, self.manager, new_scope
            )
        else:
            return SymTable(
                new_symid, glob, non_local, builtins, self.manager, new_scope
            )

    def clear(self):
        self.local = {}
        self.star_import = []
        self._tp_def = {}
        self.import_cache.clear()


class FunctionSymTable(SymTable):
    def __init__(
        self,
        symid: "SymId",
        glob: "SymTable",
        non_local: Optional["SymTable"],
        builtins: "SymTable",
        manager: "Manager",
        scope: "TableScope",
    ) -> None:
        super().__init__(symid, glob, non_local, builtins, manager, scope)
        self.param: Optional["Argument"] = None

    def lookup_local(self, name: str, search_star_import) -> Optional["TypeIns"]:
        if self.param and (arg_type := self.param.get_arg_type(name)):
            return arg_type
        return super().lookup_local(name, search_star_import=search_star_import)
