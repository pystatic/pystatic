import ast
from typing import Optional, TYPE_CHECKING, Any
from pystatic.typesys import TypeClassTemp, TypeTemp
from pystatic.symtable import SymTable, Entry, ImportNode

if TYPE_CHECKING:
    from pystatic.uri import Uri


class fake_imp_entry:
    def __init__(self, uri: 'Uri', origin_name: str,
                 defnode: ImportNode) -> None:
        self.uri = uri
        self.origin_name = origin_name
        self.defnode = defnode


def add_cls_def(symtable: SymTable, name: str, temp: TypeClassTemp):
    symtable._cls_defs[name] = temp


def add_spt_def(symtable: SymTable, name: str, temp: TypeTemp):
    symtable._spt_types[name] = temp


def add_import_item(symtable: 'SymTable', name: str, uri: 'Uri',
                    origin_name: str, defnode: 'ImportNode'):
    """
    Add import information to the symtable, this will not add entry to the
    local scope.
    """
    symtable._import_info.setdefault(uri, []).append(
        (name, origin_name, defnode))

    # add fake import entry to the local scope
    # TODO: warning if name collision happens
    tmp_entry = fake_imp_entry(uri, origin_name, defnode)
    symtable.local[name] = tmp_entry  # type: ignore


def add_fun_entry(symtable: 'SymTable', name: str, entry: Entry):
    symtable._functions.add(name)
    symtable.local[name] = entry
