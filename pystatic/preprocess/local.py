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
from pystatic.message import MessageBox
from pystatic.preprocess.def_expr import (eval_func_type, eval_typedef_expr,
                                          template_resolve_fun)


def resolve_local_typeins(symtable: 'SymTable', mbox: 'MessageBox'):
    """Resolve local symbols' TypeIns"""
    fake_data = get_fake_data(symtable)

    new_entry = {}
    for name, entry in fake_data.local.items():
        assert isinstance(entry, fake_local_entry)
        # entry may also be temporary fake_imp_entry which should not be
        # resolved here.
        defnode = entry.defnode

        option_tpins = eval_typedef_expr(defnode, symtable)
        tpins = option_tpins.value

        option_tpins.dump_to_box(mbox)

        new_entry[name] = Entry(tpins, defnode)

    symtable.local.update(new_entry)

    for tp_def in symtable._cls_defs.values():
        assert isinstance(tp_def, TypeClassTemp)
        inner_symtable = tp_def.get_inner_symtable()
        resolve_local_typeins(inner_symtable, mbox)


def resolve_local_func(symtable: 'SymTable', mbox: 'MessageBox'):
    """Resolve local function's TypeIns"""
    new_func_defs = {}

    def add_func_define(node: ast.FunctionDef):
        nonlocal symtable, new_func_defs, mbox
        option_fun = eval_func_type(node, symtable)
        func_ins = option_fun.value
        assert isinstance(func_ins, TypeFuncIns)

        option_fun.dump_to_box(mbox)

        name = node.name

        new_func_defs[name] = func_ins

        symtable.local[name] = Entry(func_ins, node)
        return func_ins

    def add_func_overload(func_ins: TypeFuncIns, argument: Argument,
                          ret: TypeIns, node: ast.FunctionDef):
        func_ins.add_overload(argument, ret)

    template_resolve_fun(symtable, add_func_define, add_func_overload, mbox)
    symtable._func_defs = new_func_defs
