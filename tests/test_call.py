# a test of call
class A:
    ...


class B:
    ...


def f1(x: A, y) -> A:
    return 1


a = B()
a = f1(a)
