"""Data structures and helper functions used in exprparse"""
import ast
from typing import (Generic, TYPE_CHECKING, List, Dict, TypeVar, Any)

if TYPE_CHECKING:
    from pystatic.typesys import TypeIns

T = TypeVar('T', bound=Any)


class WithAst(Generic[T]):
    __slots__ = ['value', 'node']

    def __init__(self, value: 'T', node: ast.AST) -> None:
        self.value = value
        self.node = node


InsWithAst = WithAst['TypeIns']


class GetItemArgs:
    __slots__ = ['items', 'node']

    def __init__(self, items: List[WithAst], node: ast.AST) -> None:
        self.items = items
        self.node = node


class ApplyArgs:
    __slots__ = ['args', 'kwargs']

    def __init__(self):
        self.args: List[InsWithAst] = []
        self.kwargs: Dict[str, InsWithAst] = {}

    def add_arg(self, tpins: 'TypeIns', node: ast.AST):
        self.args.append(InsWithAst(tpins, node))

    def add_kwarg(self, name: str, tpins: 'TypeIns', node: ast.AST):
        self.kwargs[name] = InsWithAst(tpins, node)
