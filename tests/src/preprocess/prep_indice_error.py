from typing import Callable, Literal

a: Literal[int] = 3  # E Literal's indice should be literal value
b: Literal[3] = 3
c: Callable[..., int]
d: Callable[[int], int]
e: Callable[[int, float], int]
f: Callable[int, float]  # E Parameter list doesn't match Callable's structure
g: Callable[[int], float, str]  # E Parameter list doesn't match Callable's structure
h: Callable[int]  # E Parameter list doesn't match Callable's structure
i: Callable[[2], int]  # E Expect a class type
