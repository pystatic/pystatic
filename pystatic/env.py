from contextlib import contextmanager
from typing import List
from pystatic.symtable import SymTable, TableScope


class Environment(object):
    def __init__(self, symtable: SymTable):
        assert symtable._scope == TableScope.GLOB
        self.tables: List[SymTable] = [symtable]

    @property
    def symtable(self) -> SymTable:
        return self.tables[-1]

    def new_symtable(self, scope: TableScope) -> SymTable:
        glob = self.tables[0]
        if self.symtable._scope == TableScope.FUNC:
            non_local = self.symtable
        else:
            non_local = self.symtable._non_local
        builtins = glob._builtins
        return SymTable(glob, non_local, builtins, scope)

    @contextmanager
    def enter_class(self, table: SymTable):
        assert table._scope == TableScope.CLASS
        self.tables.append(table)
        yield table
        assert self.tables
        self.tables.pop()
