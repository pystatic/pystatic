"""
Special type resolution module.
"""

import ast
import enum
import logging
from typing import Optional, Union, TYPE_CHECKING, List, Dict, Tuple
from pystatic.symtable import Entry, SymTable
from pystatic.typesys import TypeIns, TypeVar
from pystatic.visitor import val_unparse, liter_unparse
from pystatic.preprocess.type_expr import eval_type_expr
from pystatic.util import ParseException
from pystatic.typesys import TpState

logger = logging.getLogger(__name__)


class SPTKind(enum.Enum):
    """SpecialType kind

    TypeVar, TypeAlias...
    """
    TypeVar = 1
    TypeAlias = 2


def record_stp(module_uri: str, node: Union[ast.Assign, ast.AnnAssign]):
    s_type = get_stp_kind(node)
    if not s_type:
        return None, None
    else:
        if s_type == SPTKind.TypeVar:
            assert isinstance(node.value, ast.Call)
            name = get_typevar_name(node.value)
            # FIXME: the defnode given here is incorrect
            entry = Entry(TypeVar(name).get_default_type(), node.value)
            return name, entry
        else:
            assert 0, "not implemented yet"
            return None, None  # to suppress type warnings...


def get_stp_kind(node: Union[ast.Assign, ast.AnnAssign]) -> Optional[SPTKind]:
    """Return the kind of assignment node, if it's a normal assignment(not TypeVar,
    TypeAlias...), then return None"""
    if isinstance(node.value, ast.Call):
        if isinstance(node.value.func, ast.Name):
            fname = node.value.func.id
            if fname == 'TypeVar':
                return SPTKind.TypeVar
    return None


def collect_typevar_info(tpvar: TypeVar, call_expr: ast.Call,
                         symtable: SymTable) -> TypeVar:
    """Complete the content in the TypeVar which stored in tpvar and analyse
    the type constrains"""
    cons_list: List['TypeIns'] = []
    for cons_node in call_expr.args[1:]:
        try:
            cons_tp = eval_type_expr(cons_node, symtable)  # check definition
            if cons_tp:
                cons_list.append(cons_tp)
            else:
                assert 0
                # mbox.add_err(cons_node, 'failed to get type')
                pass  # TODO: warning information
        except ParseException as e:
            assert 0
            # mbox.add_err(e.node, e.msg or 'failed to get type')
            pass  # TODO: warning information

    # analyse the keyword arguments
    kw_bound = None
    kw_covariant = None
    kw_contravariant = None
    for kwarg in call_expr.keywords:
        if kwarg.arg == 'bound':
            if kw_bound:
                assert 0
                # mbox.add_err(kwarg, f'duplicate bound')
                pass
            elif len(cons_list) > 0:
                assert 0
                # mbox.add_err(kwarg, "bound and constrains can't coexist")
                pass
            else:
                try:
                    bound_ins = eval_type_expr(kwarg.value, symtable)
                except ParseException as e:
                    assert 0
                    # mbox.add_err(e.node, e.msg or f'broken type')
                    pass
                else:
                    if bound_ins is None:
                        # mbox.add_err(kwarg, 'invalid type')
                        pass
                    else:
                        kw_bound = Entry(bound_ins, kwarg.value)
        elif kwarg.arg == 'covariant':
            if kw_contravariant:
                assert 0
                # mbox.add_err(kwarg, 'covariant and contravariant is inconsist')
                pass
            else:
                try:
                    val = val_unparse(kwarg.value)
                    if isinstance(val, bool):
                        kw_covariant = val
                    else:
                        assert 0
                        # mbox.add_err(kwarg, 'bool type expected')
                        pass
                except ParseException as e:
                    assert 0
                    # mbox.add_err(kwarg, e.msg or 'broken type')
                    pass
        elif kwarg.arg == 'contravariant':
            if kw_covariant:
                assert 0
                # mbox.add_err(kwarg, 'covariant and contravariant is inconsist')
                pass
            else:
                try:
                    val = val_unparse(kwarg.value)
                    if isinstance(val, bool):
                        kw_contravariant = val
                    else:
                        assert 0
                        # mbox.add_err(kwarg, 'bool type expected')
                        pass
                except ParseException as e:
                    assert 0
                    # mbox.add_err(kwarg, e.msg or 'broken type')
                    pass
        else:
            assert 0
            # mbox.add_err(
            #     kwarg,
            #     f'keyword argument must be bound, covariant or contravariant')
            pass

    # check validity
    tpvar.constrains = cons_list

    if kw_bound:
        assert isinstance(kw_bound, Entry)
        tpvar.bound = kw_bound.get_type()
    if kw_covariant:
        assert isinstance(kw_covariant, bool)
        tpvar.covariant = True
        tpvar.contravariant = False
        tpvar.invariant = False
    elif kw_contravariant:
        assert isinstance(kw_contravariant, bool)
        tpvar.covariant = False
        tpvar.contravariant = True
        tpvar.invariant = False
    else:
        tpvar.covariant = False
        tpvar.contravariant = False
        tpvar.invariant = True

    cons_str = [str(tp) for tp in tpvar.constrains]
    bound_str = str(tpvar.bound)
    logger.debug(f'{tpvar.name} constrains: {cons_str}, bound: {bound_str}')

    return tpvar


def get_typevar_name(call_expr: ast.Call) -> str:
    if len(call_expr.args) <= 0:
        raise ParseException(call_expr,
                             f'TypeVar needs at least one parameter')

    tpvar_name = liter_unparse(call_expr.args[0])
    if not tpvar_name:
        raise ParseException(call_expr.args[0], f'invalid syntax')
    return tpvar_name


def resolve_typevar_ins(tpvar: TypeVar, node: ast.AST, symtable: 'SymTable'):
    assert isinstance(node, ast.Call)
    collect_typevar_info(tpvar, node, symtable)
    tpvar.set_state(TpState.OVER)
