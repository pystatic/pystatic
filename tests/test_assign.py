from typing import Tuple


class A:
    ...


class B:
    ...


c = a
a = A()
a = B()
b: B = A()
a, b = 1, 2, 3
