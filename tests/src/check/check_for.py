from typing import Dict, Union, Tuple, List


class A:
    ...


tpl: Tuple[int, str]
for s in tpl:
    a: int = s  # E Incompatible type in assignment(expression has type 'str', variable has type 'int')

dic: Dict[int, str]
for s in dic:
    b: A = s  # E Incompatible type in assignment(expression has type 'int', variable has type 'A')

lst: List[A]
for s in lst:
    c: int = s  # E Incompatible type in assignment(expression has type 'A', variable has type 'int')
