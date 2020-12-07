from typing import Generic, TypeVar


class A:
    pass


class B(A, A):  # E duplicate baseclass is not allowed
    pass


T = TypeVar('T', int, float)


class C(Generic[T], Generic[T, T]):  # E duplicate baseclass is not allowed
    pass
