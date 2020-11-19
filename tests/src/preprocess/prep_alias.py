from typing import Union, Optional
from extend_alias import A_ext


class A:
    def foo(self):
        self.a: int = 2


class B:
    class C:
        pass


class D(B):
    pass


Aalias = A
Balias = B
Calias = D.C
UAB = Union['A', B]
OA = Optional[A]
a = A()
b = B()
UD = 'D'
