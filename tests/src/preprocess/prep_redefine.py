class A:
    pass


class A:  # E 'A' has already defined(A previously defined at line 1)
    pass


B = 3  # E 'B' doesn't match its definition(B defined as a class at line 12)


class B:
    class C:
        pass

    class C:  # E 'C' has already defined(C previously defined at line 13)
        pass


class C:
    pass


C = 2  # E 'C' doesn't match its definition(C defined as a class at line 20)

a: int = 2
b = 3
a: str = '3'  # E 'a' has already defined(a previously defined at line 26)
c = 3  # type: int
b: str = '2'
c: int = 2  # E 'c' has already defined(c previously defined at line 29)


def f(a: int) -> int:
    pass


f: str = 3  # E 'f' has already defined(f previously defined at line 34)


def A(  # E 'A' doesn't match its definition(A defined as a class at line 1)
    a: int
) -> str:
    pass


g: int = 3  # E 'g' doesn't match its definition(g defined as a function at line 50)


def g():
    pass


def h():  # E 'h' doesn't match its definition(h defined as a class at line 58)
    pass


class h:
    pass

from typing import overload

def foo(a: int, b: str) -> str:
    pass

@overload
def foo(a: int, b: str) -> str:
    ...

@overload
def foo(a: int, b: int) -> int:
    ...

def good(a: int):
    ...

def good(a: str): # E 'good' has already defined(good previously defined at line 74)
    ...

@overload
def good(a: float):
    ...
