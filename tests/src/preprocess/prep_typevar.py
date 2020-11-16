from typing import TypeVar, Generic

T = TypeVar('T')
F = TypeVar('F', int, str)
G = TypeVar('G', bound=int)
H = TypeVar('H', bound=str, covariant=True)


class A(Generic[T]):
    pass


class B(A[F]):
    pass
