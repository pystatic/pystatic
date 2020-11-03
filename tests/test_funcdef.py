class A:
    a=1


class B:
    ...


def f1(a1: int, a2: str):
    return A


def f2() -> A:
    a = 3


def f3() -> A:
    return


def f4() -> A:
    return B()


a: int = f2()
a = 1
a += A


def f(hj: int):
    b = hj
