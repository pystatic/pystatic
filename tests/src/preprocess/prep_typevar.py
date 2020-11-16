from typing import TypeVar, Generic

T = TypeVar('T')
F = TypeVar('F', int, float)


class A(Generic[T]):
    pass


class B(A[F]):
    pass
