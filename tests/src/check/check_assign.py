class A:
    ...


a = 1
a = "hj"

b: int = "hjzs"  # E Incompatible type in assignment(expression has type 'Literal['hjzs']', variable has type 'int')
b = a  # E Incompatible type in assignment(expression has type 'Literal['hj']', variable has type 'int')
b = A()  # E Incompatible type in assignment(expression has type 'A', variable has type 'int')

c: A = A  # E Incompatible type in assignment(expression has type 'Type[A]', variable has type 'A')
c = A()


