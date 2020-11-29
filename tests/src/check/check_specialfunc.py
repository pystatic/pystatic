from typing import Union, Literal

a: Union[int, str]

if isinstance(a, int):
    b: int = a
if isinstance(a, str):
    c: str = a
