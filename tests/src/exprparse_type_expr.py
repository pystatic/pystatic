from typing import Literal, Union, Optional, Tuple, Type


class A:
    pass


a: Optional[Union[int, str]] = None
b: Optional[A] = None
c: Optional[Type[A]] = None
d: Tuple[int, ...] = (1, 2)
e: Tuple[int, str] = (1, "s")
f: Literal['test'] = 'test'
g: Tuple[Literal[1], int] = (1, 1)
