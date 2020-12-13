class A:
    def __init__(self, a: int):
        self.a = a
    
    def __lt__(self, other):
        return self.a < other.a

class B:
    def __init__(self) -> None:
        self.b = 1
    
    def __gt__(self, other):
        return self.b > other.b

    def __lt__(self, other):
        return self.b < other.b

a1: A = A()
a2: A = A()
b1: B = B()
b2: B = B()

res = a1 > a2  # E > is not supported in A

if a1 < a2:
    pass

if b1 > b2:
    pass

if b1 < b2:
    pass

a = a1 + a2  # E + is not supported in A
b = b1 - b2  # E - is not supported in B
