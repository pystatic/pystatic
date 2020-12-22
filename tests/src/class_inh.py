class A:
    def hello(self, a: int) -> int:
        return 1


class B(A):
    pass


b = B()
b.hello(3)
