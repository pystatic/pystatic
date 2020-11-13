from typing import Tuple

a, b = ()  # E Need more values to unpack(expected 2, got 0)
a, b = 1  # E Need more values to unpack(expected 2, got 1)
a, b = (1, 2, 3)  # E Too more values to unpack(expected 2, got 3)
a, b = (1, 2, 3, 4)  # E Too more values to unpack(expected 2, got 4)
a, b = 1, 2

c: int = 1
d: str = "s"
c, d = 1, 2  # E Incompatible type in assignment(expression has type 'int', variable has type 'str')
d, c = 1, 2  # E Incompatible type in assignment(expression has type 'int', variable has type 'str')

t1: Tuple[int, str] = (1, "s")
t1 = ("s", 1)# E Incompatible type in assignment(expression has type 'Tuple[str,int]', variable has type 'Tuple[int,str]')
t1 = 1  # E Incompatible type in assignment(expression has type 'Literal[1]', variable has type 'Tuple[int,str]')
t1 = "s"  # E Incompatible type in assignment(expression has type 'Literal['s']', variable has type 'Tuple[int,str]')


class A:
    ...


class B:
    ...


t2: Tuple[A, B] = A, B # E Incompatible type in assignment(expression has type 'Tuple[Type[A],Type[B]]', variable has type 'Tuple[A,B]')
t2 = A(), B()
t2 = A(), B  # E Incompatible type in assignment(expression has type 'Tuple[A,Type[B]]', variable has type 'Tuple[A,B]')
t2 = B(), A()  # E Incompatible type in assignment(expression has type 'Tuple[B,A]', variable has type 'Tuple[A,B]')