import ast
import enum
import logging
from typing import Optional, Union, TYPE_CHECKING, List, Dict, Tuple
from pystatic.symtable import Entry, SymTable
from pystatic.typesys import TypeIns, TypeVar
from pystatic.message import MessageBox
from pystatic.visitor import val_unparse, liter_unparse
from pystatic.preprocess.annotation import parse_annotation
from pystatic.util import ParseException

if TYPE_CHECKING:
    from pystatic.env import Environment

logger = logging.getLogger(__name__)


class SpecialTypeKind(enum.Enum):
    """Special types

    TypeVar, TypeAlias...
    """
    TypeVar = 1
    TypeAlias = 2


def try_special_type(node: Union[ast.Assign,
                                 ast.AnnAssign], vardict: Dict[str, Entry],
                     symtable: SymTable, mbox: 'MessageBox') -> bool:
    s_type = get_special_type_kind(node)
    if not s_type:
        return False
    else:
        analyse_special_type(s_type, node, vardict, symtable, mbox)
        return True


def get_special_type_kind(
        node: Union[ast.Assign, ast.AnnAssign]) -> Optional[SpecialTypeKind]:
    """Return the kind of assignment node, if it's a normal assignment(not TypeVar,
    TypeAlias...), then return None"""
    if isinstance(node.value, ast.Call):
        if isinstance(node.value.func, ast.Name):
            fname = node.value.func.id
            if fname == 'TypeVar':
                return SpecialTypeKind.TypeVar
    return None


def analyse_special_type(kind: SpecialTypeKind, node: Union[ast.Assign,
                                                            ast.AnnAssign],
                         vardict: Dict[str, Entry], symtable: SymTable,
                         mbox: 'MessageBox'):
    if kind == SpecialTypeKind.TypeVar:
        analyse_typevar(node, vardict, symtable, mbox)
    else:
        assert 0, "Not implemented yet"


def analyse_typevar(node: Union[ast.Assign, ast.AnnAssign],
                    vardict: Dict[str, Entry], symtable: 'SymTable',
                    mbox: 'MessageBox') -> Optional[TypeVar]:
    assert isinstance(node.value, ast.Call)
    try:
        tpvar = collect_typevar_info(node.value, symtable, mbox)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                try:
                    var_name = liter_unparse(target)
                    assert var_name
                    if var_name != tpvar.name:
                        mbox.add_err(target,
                                     f"{var_name} doesn't match {tpvar.name}")
                    else:
                        vardict[var_name] = Entry(tpvar.get_type(), target)
                except ParseException as e:
                    mbox.add_err(target, e.msg or 'syntax error')
        else:
            # TODO: analyse annotation
            var_name = liter_unparse(node.target)
            if var_name != tpvar.name:
                mbox.add_err(node.target,
                             f"{var_name} doesn't match {tpvar.name}")
    except ParseException as e:
        mbox.add_err(e.node, e.msg or '')


def collect_typevar_info(call_expr: ast.Call, symtable: SymTable,
                         mbox: 'MessageBox') -> TypeVar:
    tpvar_name = get_typevar_name(call_expr)
    tpvar = TypeVar(tpvar_name)  # FIXME: name may be wrong

    # complete the content in the TypeVar which stored in tpvar
    # analyse the type constrains
    cons_list: List['Entry'] = []
    for cons_node in call_expr.args[1:]:
        try:
            cons_tp = parse_annotation(cons_node, symtable)  # check definition
            if cons_tp:
                cons_list.append(Entry(cons_tp, cons_node))
            else:
                mbox.add_err(cons_node, 'failed to get type')
        except ParseException as e:
            mbox.add_err(e.node, e.msg or 'failed to get type')

    # analyse the keyword arguments
    kw_bound = None
    kw_covariant = None
    kw_contravariant = None
    for kwarg in call_expr.keywords:
        if kwarg.arg == 'bound':
            if kw_bound:
                mbox.add_err(kwarg, f'duplicate bound')
            elif len(cons_list) > 0:
                mbox.add_err(kwarg, "bound and constrains can't coexist")
            else:
                try:
                    bound_ins = parse_annotation(kwarg.value, symtable)
                except ParseException as e:
                    mbox.add_err(e.node, e.msg or f'broken type')
                else:
                    if bound_ins is None:
                        mbox.add_err(kwarg, 'invalid type')
                    else:
                        kw_bound = Entry(bound_ins, kwarg.value)
        elif kwarg.arg == 'covariant':
            if kw_contravariant:
                mbox.add_err(kwarg, 'covariant and contravariant is inconsist')
            else:
                try:
                    val = val_unparse(kwarg.value)
                    if isinstance(val, bool):
                        kw_covariant = val
                    else:
                        mbox.add_err(kwarg, 'bool type expected')
                except ParseException as e:
                    mbox.add_err(kwarg, e.msg or 'broken type')
        elif kwarg.arg == 'contravariant':
            if kw_covariant:
                mbox.add_err(kwarg, 'covariant and contravariant is inconsist')
            else:
                try:
                    val = val_unparse(kwarg.value)
                    if isinstance(val, bool):
                        kw_contravariant = val
                    else:
                        mbox.add_err(kwarg, 'bool type expected')
                except ParseException as e:
                    mbox.add_err(kwarg, e.msg or 'broken type')
        else:
            mbox.add_err(
                kwarg,
                f'keyword argument must be bound, covariant or contravariant')

    # check validity
    for cons in cons_list:
        if isinstance(cons.get_real_type(), Deferred):
            symtable.add_anon_entry(cons)
    tpvar.constrains = cons_list

    if kw_bound:
        assert isinstance(kw_bound, Entry)
        tpvar.bound = kw_bound
        if isinstance(kw_bound.get_real_type(), Deferred):
            symtable.add_anon_entry(kw_bound)
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

    return tpvar


def get_typevar_name(call_expr: ast.Call) -> str:
    if len(call_expr.args) <= 0:
        raise ParseException(call_expr,
                             f'TypeVar needs at least one parameter')

    tpvar_name = liter_unparse(call_expr.args[0])
    if not tpvar_name:
        raise ParseException(call_expr.args[0], f'invalid syntax')
    return tpvar_name
