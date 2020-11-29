from typing import Union

a: Union[int, str]

if isinstance(a, int):
    b: int = a
elif isinstance(a, str):
    c: str = a
