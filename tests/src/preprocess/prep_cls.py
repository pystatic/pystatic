class A:
    @staticmethod
    def static_foo(a, b: int) -> int:
        return 1

    @classmethod
    def class_foo(cls):
        pass

    def __init__(self, a: int) -> None:
        self.a = a


a: A = A()
