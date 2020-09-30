"""
Resolve type instance for symbols defined locally.
"""

import ast
import logging
from pystatic.symtable import SymTable
from pystatic.typesys import TpState, TypeClassTemp, any_ins, TypeVar
from pystatic.symtable import Entry
from pystatic.preprocess.type_expr import eval_type_expr
from pystatic.preprocess.spt import resolve_typevar_ins

logger = logging.getLogger(__name__)


def resolve_local_typeins(symtable: 'SymTable'):
    """Resolve local symbols' TypeIns, here 'local' means defined inside the scope"""
    for name, entry in symtable.local.items():
        if isinstance(entry, Entry):
            # entry may also be temporary fake_imp_entry which should not be
            # resolved here.
            cur_type = entry.get_type()
            if entry.get_type() is None:
                typenode = entry.get_defnode()
                if typenode:
                    var_type = eval_type_expr(typenode, symtable)
                    if var_type:
                        entry.set_type(var_type.getins())
                        logger.debug(f'{name}: {var_type}')
                    else:
                        # TODO: warning here
                        entry.set_type(any_ins)
                        logger.debug(f'{name}: {any_ins}')
                else:
                    entry.set_type(any_ins)
                    logger.debug(f'{name}: {any_ins}')
            elif isinstance(
                    cur_type.temp,
                    TypeVar) and cur_type.temp.get_state() == TpState.FRESH:
                defnode = entry.get_defnode()
                assert defnode
                resolve_typevar_ins(cur_type.temp, defnode, symtable)

    for tp_def in symtable._cls_defs.values():
        assert isinstance(tp_def, TypeClassTemp)
        inner_symtable = tp_def.get_inner_symtable()
        resolve_local_typeins(inner_symtable)
