from typing import Tuple

a: int = 1
b: int = 2


class B:
    pass


class A:
    def __add__(self, other) -> B:
        return B()


c: A = A()
d: B = B()

e: Tuple[int] = (3, )
f: Tuple[str, int] = ('hello', 3)
