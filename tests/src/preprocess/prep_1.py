class A:
    def __init__(self) -> None:
        self.a: int = 1

    class B:
        pass


class B:
    pass


a: A
a = A()


def f(a: B, c: A) -> A:
    return A()


c, d = 1, 2
e = A()  # type: A
g = B()  # type: A.B
