class A:
    ...


class B:
    ...


def f1():
    return A


def f2() -> A:
    a = 3


def f3() -> A:
    return

def f4() -> A:
    return B()


a: B = f2()
