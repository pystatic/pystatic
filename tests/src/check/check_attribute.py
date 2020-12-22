class A:
    c = 1

    def __init__(self):
        self.a: int = 1
        self.b = "s"


# a: A = A()
# a.a = "s"  # E Incompatible type in assignment(expression has type 'Literal['s']', variable has type 'int')
# a.b = 1

b = A
b.a = "s"  # E Type 'Type[A]' has no attribute 'a'
b.c = 1
