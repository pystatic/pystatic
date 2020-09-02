import ast
import enum
import logging
from typing import Optional, Union, TYPE_CHECKING, List
from pystatic.typesys import TypeIns, TypeVar
from pystatic.util import (BaseVisitor, liter_unparse, val_unparse,
                           ParseException)
from pystatic.preprocess.annotation import (get_type_from_snode, parse_ann_ast,
                                            parse_annotation)

if TYPE_CHECKING:
    from pystatic.env import Environment

logger = logging.getLogger(__name__)


class SType(enum.Enum):
    """Special types

    TypeVar, TypeAlias...
    """
    TypeVar = 1
    TypeAlias = 2


def special_typing_kind(
        node: Union[ast.Assign, ast.AnnAssign]) -> Optional[SType]:
    """Return the kind of assignment node, if it's a normal assignment(not TypeVar,
    TypeAlias...), then return None"""
    if isinstance(node.value, ast.Call):
        if isinstance(node.value.func, ast.Name):
            fname = node.value.func.id
            if fname == 'TypeVar':
                return SType.TypeVar
    return None


def analyse_special_typing(kind: SType, node: Union[ast.Assign, ast.AnnAssign],
                           env: 'Environment'):
    if kind == SType.TypeVar:
        analyse_typevar(node, env)
    else:
        assert 0, "Not implemented yet"


def analyse_typevar(node: Union[ast.Assign, ast.AnnAssign],
                    env: 'Environment'):
    assert isinstance(node.value, ast.Call)
    try:
        tpvar = collect_typevar_info(node.value, env)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                var_name = liter_unparse(target)
                if var_name != tpvar.name:
                    env.add_err(target,
                                f"{var_name} doesn't match {tpvar.name}")
        else:
            # TODO: analyse annotation
            var_name = liter_unparse(node.target)
            if var_name != tpvar.name:
                env.add_err(node.target,
                            f"{var_name} doesn't match {tpvar.name}")
    except ParseException as e:
        env.add_err(e.node, e.msg or '')


def collect_typevar_info(call_expr: ast.Call, env: 'Environment') -> TypeVar:
    if len(call_expr.args) <= 0:
        raise ParseException(call_expr, f'TypeVar need at least one parameter')

    tpvar_name = liter_unparse(call_expr.args[0])
    if tpvar_name:
        tpvar = env.lookup_local_type(tpvar_name)
        assert tpvar.name == tpvar_name
        if not tpvar or not isinstance(tpvar, TypeVar):
            raise ParseException(call_expr.args[0], f'{tpvar_name} unbound')
    else:
        raise ParseException(call_expr.args[0], f'invalid syntax')

    # complete the content in the TypeVar which stored in tpvar
    # analyse the type constrains
    cons_list: List[TypeIns] = []
    for cons_node in call_expr.args[1:]:
        try:
            cons_tp = parse_annotation(cons_node, env,
                                       True)  # check definition
            if cons_tp:
                cons_list.append(cons_tp)
            else:
                env.add_err(cons_node, 'failed to get type')
        except ParseException as e:
            env.add_err(e.node, e.msg or 'failed to get type')

    # analyse the keyword arguments
    kw_bound = None
    kw_covariant = None
    kw_contravariant = None
    for kwarg in call_expr.keywords:
        if kwarg.arg == 'bound':
            if kw_bound:
                env.add_err(kwarg, f'duplicate bound')
            elif len(cons_list) > 0:
                env.add_err(kwarg, "bound and constrains can't coexist")
            else:
                try:
                    kw_bound = parse_annotation(kwarg.value, env, False)
                except ParseException as e:
                    env.add_err(e.node, e.msg or f'broken type')
                else:
                    if kw_bound is None:
                        env.add_err(kwarg, 'invalid type')
        elif kwarg.arg == 'covariant':
            if kw_contravariant:
                env.add_err(kwarg, 'covariant and contravariant is inconsist')
            else:
                try:
                    val = val_unparse(kwarg.value)
                    if isinstance(val, bool):
                        kw_contravariant = val
                    else:
                        env.add_err(kwarg, 'bool type expected')
                except ParseException as e:
                    env.add_err(kwarg, e.msg or 'broken type')
        elif kwarg.arg == 'contravariant':
            if kw_covariant:
                env.add_err(kwarg, 'covariant and contravariant is inconsist')
            else:
                try:
                    val = val_unparse(kwarg.value)
                    if isinstance(val, bool):
                        kw_covariant = val
                    else:
                        env.add_err(kwarg, 'bool type expected')
                except ParseException as e:
                    env.add_err(kwarg, e.msg or 'broken type')
        else:
            env.add_err(
                kwarg,
                f'keyword argument must be bound, covariant or contravariant')

    # check validity
    tpvar.constrains = cons_list

    if kw_bound:
        assert isinstance(kw_bound, TypeIns)
        tpvar.bound = kw_bound
    if kw_covariant:
        assert isinstance(kw_covariant, bool)
        tpvar.covariant = True
    elif kw_contravariant:
        assert isinstance(kw_contravariant, bool)
        tpvar.contravariant = True
    else:
        tpvar.invariant = True

    return tpvar
