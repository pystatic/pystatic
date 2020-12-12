a = 1
a(3)  # E Literal[1] is not callable

def foo1(a: int, b: int) -> str:
    return 'hello'

def foo2(a: int, b: int, *args: int) -> str:
    return 'world'

def foo3(a: int, b: str) -> str:
    return ''

foo1(1, 2)
foo1(1, 2, 3)  # E Too more arguments
foo1(1)  # E Too few arguments(missing b)
foo2(1, 2, 3)
foo2(1)  # E Too few arguments(missing b)
foo2(1, 2)
foo3(1, 1)  # E Incompatible type for parameter b(get 'Literal[1]', expect 'str')

def foo4(a: int, *args: int):
    return None

foo4(1, '3')  # E Incompatible type for parameter *args(get 'Literal['3']', expect 'int')

def foo5(a: int, b: str):
    return None

foo5(b='good', a=1)

def foo6(a: int, b: int, *args, c: int):
    return None

foo6(1, 2, c='3') # E Incompatible type for parameter c(get 'Literal['3']', expect 'int')
foo6(1, 2, 3)  # E Too few arguments(missing c)
foo6(1, 2, c=3)

def foo7(a: int, b, *args, c: int, **kwargs: bool):
    return None

foo7(a=1, b=2, c=3, d=4)  # E Incompatible type for parameter **kwargs(get 'Literal[4]', expect 'bool')
foo7(1, 'hello', 3, c=2, d=True)
