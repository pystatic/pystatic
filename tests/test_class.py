class B:
    ...


b: B = B()


class A:
    a: int = 1

    def __init__(self):
        self.p1 = B()

    def fun(self):
        pass

def f():
    pass
