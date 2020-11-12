from typing import Union


class A:
    ...


a = c  # E Cannot determine type of 'c'(unresolved reference 'c')
a = 1
a = "s"  # ok

b: int = "hjzs"  # E Incompatible type in assignment(expression has type 'Literal['hjzs']', variable has type 'int')
b = a  # E Incompatible type in assignment(expression has type 'Literal['s']', variable has type 'int')
b = A()  # E Incompatible type in assignment(expression has type 'A', variable has type 'int')

c: A = A  # E Incompatible type in assignment(expression has type 'Type[A]', variable has type 'A')
c = A()

t1 = "s"
if A:
    t1 = 1
t2: int = t1  # ok

t3: int = "s"  # E Incompatible type in assignment(expression has type 'Literal['s']', variable has type 'int')
t4: int = t3  # ok

#
# t5: Union[int, str] = 1
# t5 = "s"
# t5 = A()
# t6: str = t5
# t7: int = t5
