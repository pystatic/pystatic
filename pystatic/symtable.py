import ast
import enum
from typing import Union, Dict, TYPE_CHECKING, Set, Optional
from pystatic.moduri import ModUri
from pystatic.typesys import TPointer, Tdefer


if TYPE_CHECKING:
    from pystatic.typesys import TypeIns

class Tabletype(enum.Enum):
    GLOB = 1
    CLASS = 2
    FUNC = 3

class Entry:
    def __init__(self, def_node: ast.AST, tp: Union[Tdefer, 'TypeIns']) -> None:
        self.def_node = def_node
        self.tnode = TPointer(tp)


class SymTable:
    """Symbol table"""
    def __init__(self, glob: 'SymTable', non_local: 'SymTable',
                 builtins: 'SymTable', table_type: 'Tabletype') -> None:
        self.local: Dict[str, Entry] = {}
        self.non_local = non_local
        self.global = glob
        self.builtins = builtins

        self.table_type = table_type

        self.defer: Set[TPointer] = set()

    def add_entry(self, name: str, def_node: ast.AST, tp: TypeIns):
        self.local[name] = Entry(def_node, tp)

    def get_local_entry(self, name: str) -> Optional[Entry]:
        return self.local.get(name)
