from typing import Callable, Generic, Literal, List, Dict, Tuple, TypeVar

a: Literal[int] = 3  # E Literal's indice should be literal value
b: Literal[3] = 3
c: Callable[..., int]
d: Callable[[int], int]
e: Callable[[int, float], int]
f: Callable[int, float]  # E Parameter list doesn't match Callable's structure
g: Callable[[int], float, str]  # E Parameter list doesn't match Callable's structure
h: Callable[int]  # E Parameter list doesn't match Callable's structure
i: Callable[[2], int]  # E Expect a class type
j: List[int, float] # E receive 2 but require 1 argument(s)
k: Dict[int, float]
l: Tuple[int, int, float]
m: List['int']
n: List[1]  # E Expect a class type
o: Dict[[int], float]  # E Expect a class type
p: Tuple[...]  # E '...' allowed only as the second of two arguments

T = TypeVar('T', int, float)
class A(Generic[T]):
    ...

class B(Generic[T, int]):  # E Expect a TypeVar
    ...

class C(Generic[T, 1]):  # E Expect a TypeVar
    ...
