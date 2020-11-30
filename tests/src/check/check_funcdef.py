def f1():
    return "s"


def f2() -> int:
    return "s"  # E Incompatible return value type(expected 'int', got 'Literal['s']')


def f3() -> int:  # E Return value expected
    a: int = 1


def f4() -> None:
    return


def f5() -> None:
    a = 1


from typing import Dict, Union, Tuple
class A:
    ...

dic: Tuple[int, str, A]
for s in dic:
    a: A = s
    break
    f=1
