from contextlib import contextmanager
from typing import List
from pystatic.symtable import SymTable, Tabletype


class Environment(object):
    def __init__(self, symtable: SymTable):
        assert symtable.table_type == Tabletype.GLOB
        self.tables: List[SymTable] = [symtable]

    @property
    def symtable(self) -> SymTable:
        return self.tables[-1]

    def new_symtable(self, table_type: Tabletype) -> SymTable:
        glob = self.tables[0]
        if self.symtable.table_type == Tabletype.FUNC:
            non_local = self.symtable
        else:
            non_local = self.symtable.non_local
        builtins = glob.builtins
        return SymTable(glob, non_local, builtins, table_type)

    @contextmanager
    def enter_class(self, table: SymTable):
        assert table.table_type == Tabletype.CLASS
        self.tables.append(table)
        yield table
        assert self.tables
        self.tables.pop()
