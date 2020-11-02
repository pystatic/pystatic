from tests.test_import import C1
from tests import test_import


class A:
    def __init__(self):
        self.a: int = 1
        self.b: str = 1
        self.b = C1()
        self.b = test_import.C1.my
        self.b = test_import.C1().my


class B:
    ...


t = "sdfsf"
t = 1

cls_a: A = B()
cls_a = C
cls_a.c = "dsdfsd"
cls_a.b = False
cls_a.b = t

b: B = B()
a: A = cls_a

if isinstance(a, B):
    s = 1
if isinstance(b, B):
    s = 1


def fun() -> int:
    return "sdfs"


def fun1() -> int:
    if False:
        return "dsf"
    return True


def fun2() -> int:
    if True:
        return "dsf"
    return 1


def fun3() -> int:
    if a < 1:
        return "asd"
    else:
        return A


while True:
    if b < 1:
        hj = 1
        yy = 2
        if False:
            a = 1
            break
        b = 3
        if True:
            break
        s = 2
    else:
        aaa = 2
        break
        s = 1
    bb = 3

t = "dsfs"
if t:
    a = 1
