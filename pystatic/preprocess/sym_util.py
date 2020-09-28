import ast
from typing import Optional
from pystatic.typesys import TypeClassTemp, TypeTemp
from pystatic.symtable import SymTable, Entry
from pystatic.uri import Uri


def add_cls_def(symtable: SymTable, name: str, temp: TypeClassTemp):
    symtable._cls_defs[name] = temp


def add_spt_def(symtable: SymTable, name: str, temp: TypeTemp):
    symtable._spt_types[name] = temp


def add_import_item(symtable: 'SymTable', name: str, uri: 'Uri',
                    origin_name: str, defnode: ast.AST):
    """Add import information to the symtable"""
    symtable.local[name] = Entry(None, defnode)  # TODO: name collision?
    symtable._import_info.setdefault(uri, []).append((name, origin_name))


def add_fun_entry(symtable: 'SymTable', name: str, entry: Entry):
    symtable._functions.add(name)
    symtable.local[name] = entry
