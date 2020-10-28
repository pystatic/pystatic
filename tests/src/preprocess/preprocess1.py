class A:
    def __init__(self) -> None:
        self.a: int = 1


class B:
    pass


a: A = A()


def f(a: B, c: A) -> A:
    return A()
