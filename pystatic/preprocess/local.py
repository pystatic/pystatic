"""
Resolve type instance for symbols defined locally.
"""

import ast
import logging
from typing import Any
from pystatic.preprocess.sym_util import fake_fun_entry, fake_local_entry
from pystatic.symtable import SymTable
from pystatic.typesys import TpState, TypeClassTemp, any_ins, TypeVar
from pystatic.symtable import Entry
from pystatic.preprocess.type_expr import eval_type_expr
from pystatic.preprocess.spt import resolve_typevar_ins

logger = logging.getLogger(__name__)


def resolve_local_typeins(symtable: 'SymTable'):
    """Resolve local symbols' TypeIns, here 'local' means defined inside the scope"""
    new_entry = {}
    for name, entry in symtable.local.items():
        entry: Any
        if isinstance(entry, fake_fun_entry) or isinstance(
                entry, fake_local_entry):
            # entry may also be temporary fake_imp_entry which should not be
            # resolved here.
            defnode = entry.defnode
            assert defnode
            var_type = eval_type_expr(defnode, symtable)
            if var_type:
                tpins = var_type.getins()
            else:
                # TODO warning here
                tpins = any_ins
            new_entry[name] = Entry(tpins, defnode)
            logger.debug(f'({symtable.uri}) {name}: {tpins}')

    symtable.local.update(new_entry)

    for tp_def in symtable._cls_defs.values():
        assert isinstance(tp_def, TypeClassTemp)
        inner_symtable = tp_def.get_inner_symtable()
        resolve_local_typeins(inner_symtable)
