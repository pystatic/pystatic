from typing import Union, Optional, Tuple, Type


class A:
    pass


a: Optional[Union[int, str]] = None
b: Optional[A] = None
c: Optional[Type[A]] = None
d: Tuple[int, str, ...] = (1, 2)
