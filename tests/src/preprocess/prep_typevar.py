from typing import TypeVar, Generic
from .extend_typevar import I

T = TypeVar('T')
F = TypeVar('F', 'int', str)
G = TypeVar('G', bound=int)
H = TypeVar('H', bound=str, covariant=True)


class A(Generic[T, G, H, I]):
    pass


class B(A[F, int, str]):
    pass
