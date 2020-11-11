"""Data structures and helper functions used in exprparse"""
import ast
from typing import (Generic, TYPE_CHECKING, List, Dict, Tuple, Union, TypeVar,
                    Any, Sequence)

if TYPE_CHECKING:
    from pystatic.typesys import TypeIns
    from pystatic.arg import Argument

T = TypeVar('T', bound=Any)


class WithAst(Generic[T]):
    __slots__ = ['ins', 'node']

    def __init__(self, tpins: 'T', node: ast.AST) -> None:
        self.ins = tpins
        self.node = node


InsWithAst = WithAst['TypeIns']
GetItemArg = WithAst[Union[Tuple['GetItemArg'], List['GetItemArg'], 'TypeIns']]


class ApplyArgs:
    __slots__ = ['args', 'kwargs']

    def __init__(self):
        self.args: List[InsWithAst] = []
        self.kwargs: Dict[str, InsWithAst] = {}

    def add_arg(self, tpins: 'TypeIns', node: ast.AST):
        self.args.append(InsWithAst(tpins, node))

    def add_kwarg(self, name: str, tpins: 'TypeIns', node: ast.AST):
        self.kwargs[name] = InsWithAst(tpins, node)


ApplyResult = Tuple[Dict[str, InsWithAst], List[InsWithAst], Dict[str,
                                                                  InsWithAst]]


def apply(param: 'Argument', applyargs: ApplyArgs) -> ApplyResult:
    i = 0
    arg_len = len(applyargs.args)
    origin_res = {}
    apply_args = applyargs.args
    apply_kwargs = applyargs.kwargs

    for arg in param.posonlyargs:
        if i >= arg_len:
            assert False, "TODO"

        origin_res[arg.name] = apply_args[i]
        i += 1

    used_kwarg = set()
    for arg in param.args:
        if i < arg_len:
            origin_res[arg.name] = apply_args[i]
            i += 1
        else:
            if arg.name in apply_kwargs:
                origin_res[arg.name] = apply_kwargs[arg.name]
                used_kwarg.add(arg.name)
            else:
                assert False, "TODO"

    star_arg_res = apply_args[i:]  # *args

    for arg in param.kwonlyargs:
        if arg.name in apply_kwargs:
            origin_res[arg.name] = apply_kwargs[arg.name]
            used_kwarg.add(arg.name)
        else:
            assert False, "TODO"

    star_kw_res = {
        name: ins
        for name, ins in apply_kwargs.items() if name not in used_kwarg
    }  # *kwargs, name that used before should not be collected here

    return origin_res, star_arg_res, star_kw_res
