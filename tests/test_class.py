class B:
    ...


class A:
    def __init__(self):
        self.p1 = B()

    def f(self):
        self.a = 1


A.a = 1
