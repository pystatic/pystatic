from contextlib import contextmanager
from typing import List
from pystatic.symtable import SymTable, Tabletype


class Environment(object):
    def __init__(self, symtable: SymTable):
        self.tables: List[SymTable] = [symtable]

    @property
    def symtable(self) -> SymTable:
        return self.tables[-1]

    @contextmanager
    def enter_class(self, table: SymTable):
        assert table.table_type == Tabletype.CLASS
        self.tables.append(table)
        yield
        assert self.tables
        self.tables.pop()
