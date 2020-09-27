import ast
import logging
from pystatic.symtable import SymTable
from pystatic.typesys import TpState, TypeClassTemp, any_ins, TypeVar
from pystatic.preprocess.type_expr import eval_type_expr
from pystatic.preprocess.special_type import collect_typevar_info

logger = logging.getLogger()


def resolve_local_typeins(symtable: 'SymTable'):
    for name, entry in symtable.local.items():
        cur_type = entry.get_type()
        if entry.get_type() is None:
            typenode = entry.get_typenode()
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

    for tp_def in symtable.cls_defs.values():
        assert isinstance(tp_def, TypeClassTemp)
        inner_symtable = tp_def.get_inner_symtable()
        resolve_local_typeins(inner_symtable)


def resolve_import_ins():
    pass


def resolve_typevar_ins(tpvar: TypeVar, node: ast.AST, symtable: 'SymTable'):
    assert isinstance(node, ast.Call)
    collect_typevar_info(tpvar, node, symtable)
    tpvar.set_state(TpState.OVER)
