from pystatic.symtable import SymTable
from pystatic.preprocess.annotation import parse_annotation
from pystatic.typesys import any_ins


def resolve_typeins(symtable: 'SymTable'):
    for entry in symtable.local.values():
        if entry.get_type() is None:
            typenode = entry.get_typenode()
            if typenode:
                var_type = parse_annotation(typenode, symtable)
                entry.set_type(var_type)
            else:
                entry.set_type(any_ins)
