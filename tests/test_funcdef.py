class A:
    ...


class B:
    ...




def f1():
    return A()


def f2() -> B:
    return A()


a: B = f1()
