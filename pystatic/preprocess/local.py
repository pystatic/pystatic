"""
Resolve type instance for symbols defined locally.
"""

import ast
import logging
from pystatic.arg import Argument
from typing import Any, Optional, overload
from pystatic.preprocess.sym_util import *
from pystatic.symtable import SymTable
from pystatic.typesys import (TypeClassTemp, TypeFuncIns, any_ins, TypeIns)
from pystatic.symtable import Entry
from pystatic.preprocess.type_expr import (eval_func_type, eval_type_def_expr,
                                           template_resolve_fun)

logger = logging.getLogger(__name__)


def resolve_local_typeins(symtable: 'SymTable'):
    """Resolve local symbols' TypeIns"""
    fake_data = get_fake_data(symtable)

    new_entry = {}
    for name, entry in fake_data.local.items():
        assert isinstance(entry, fake_local_entry)
        # entry may also be temporary fake_imp_entry which should not be
        # resolved here.
        defnode = entry.defnode

        var_type = eval_type_def_expr(defnode, symtable)
        if var_type:
            func_ins = var_type.getins()
        else:
            # TODO warning here
            func_ins = any_ins
        new_entry[name] = Entry(func_ins, defnode)
        logger.debug(f'({symtable.uri}) {name}: {func_ins}')

    symtable.local.update(new_entry)

    for tp_def in symtable._cls_defs.values():
        assert isinstance(tp_def, TypeClassTemp)
        inner_symtable = tp_def.get_inner_symtable()
        resolve_local_typeins(inner_symtable)


def resolve_local_func(symtable: 'SymTable'):
    """Resolve local function's TypeIns"""
    new_func_defs = {}

    def add_func_define(node: ast.FunctionDef):
        nonlocal symtable, new_func_defs
        func_ins = eval_func_type(node, symtable)
        assert isinstance(func_ins, TypeFuncIns)
        name = node.name

        new_func_defs[name] = func_ins

        symtable.local[name] = Entry(func_ins, node)
        logger.debug(f'({symtable.uri}) {name}: {func_ins}')
        return func_ins

    def add_func_overload(func_ins: TypeFuncIns, argument: Argument,
                          ret: TypeIns, node: ast.FunctionDef):
        func_ins.add_overload(argument, ret)
        logger.debug(
            f'overload ({symtable.uri}) {node.name}: {func_ins.str_expr(None)}'
        )

    template_resolve_fun(symtable, add_func_define, add_func_overload)
    symtable._func_defs = new_func_defs
