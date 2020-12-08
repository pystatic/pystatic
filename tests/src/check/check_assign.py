from typing import Union, Literal


class A:
    ...


# value undefined
a = c  # E Cannot determine type of 'c'(unresolved reference 'c')

# any
a = 1
a = "s"  # ok

b: int = "hjzs"  # E Incompatible type in assignment(expression has type 'Literal['hjzs']', variable has type 'int')
b = a  # E Incompatible type in assignment(expression has type 'Literal['s']', variable has type 'int')
b = A()  # E Incompatible type in assignment(expression has type 'A', variable has type 'int')

# type[A] and A
c: A = A  # E Incompatible type in assignment(expression has type 'Type[A]', variable has type 'A')
c = A()

# t1 = "s"
# if A:
#     t1 = A()
# t2: int = t1

t3: int = "s"  # E Incompatible type in assignment(expression has type 'Literal['s']', variable has type 'int')
t4: int = t3  # ok

d: Literal[1] = 1
