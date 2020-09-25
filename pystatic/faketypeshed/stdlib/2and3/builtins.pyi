import sys
from typing import (Optional, Union, Text, SupportsInt, SupportsIndex, Literal,
                    Tuple, overload, Iterable, Protocol, SupportsBytes, Any)


class _SupportsIndex(Protocol):
    def __index__(self) -> int:
        ...


class int:
    @overload
    def __init__(
            self,
            x: Union[Text, bytes, SupportsInt, _SupportsIndex] = ...) -> None:
        ...

    @overload
    def __init__(self, x: Union[Text, bytes, bytearray], base: int) -> None:
        ...

    if sys.version_info >= (3, 8):

        def as_integer_ratio(self) -> Tuple[int, Literal[1]]:
            ...

    @property
    def real(self) -> int:
        ...

    @property
    def imag(self) -> int:
        ...

    @property
    def numerator(self) -> int:
        ...

    @property
    def denominator(self) -> int:
        ...

    def conjugate(self) -> int:
        ...

    def bit_length(self) -> int:
        ...

    if sys.version_info >= (3, ):

        def to_bytes(self,
                     length: int,
                     byteorder: str,
                     *,
                     signed: bool = ...) -> bytes:
            ...

        @classmethod
        def from_bytes(cls,
                       bytes: Union[Iterable[int], SupportsBytes],
                       byteorder: str,
                       *,
                       signed: bool = ...) -> int:
            ...  # TODO buffer object argument

    def __add__(self, x: int) -> int:
        ...

    def __sub__(self, x: int) -> int:
        ...

    def __mul__(self, x: int) -> int:
        ...

    def __floordiv__(self, x: int) -> int:
        ...

    if sys.version_info < (3, ):

        def __div__(self, x: int) -> int:
            ...

    def __truediv__(self, x: int) -> float:
        ...

    def __mod__(self, x: int) -> int:
        ...

    def __divmod__(self, x: int) -> Tuple[int, int]:
        ...

    def __radd__(self, x: int) -> int:
        ...

    def __rsub__(self, x: int) -> int:
        ...

    def __rmul__(self, x: int) -> int:
        ...

    def __rfloordiv__(self, x: int) -> int:
        ...

    if sys.version_info < (3, ):

        def __rdiv__(self, x: int) -> int:
            ...

    def __rtruediv__(self, x: int) -> float:
        ...

    def __rmod__(self, x: int) -> int:
        ...

    def __rdivmod__(self, x: int) -> Tuple[int, int]:
        ...

    @overload
    def __pow__(self, __x: Literal[2], __modulo: Optional[int] = ...) -> int:
        ...

    @overload
    def __pow__(self, __x: int, __modulo: Optional[int] = ...) -> Any:
        ...  # Return type can be int or float, depending on x.

    def __rpow__(self, x: int, mod: Optional[int] = ...) -> Any:
        ...

    def __and__(self, n: int) -> int:
        ...

    def __or__(self, n: int) -> int:
        ...

    def __xor__(self, n: int) -> int:
        ...

    def __lshift__(self, n: int) -> int:
        ...

    def __rshift__(self, n: int) -> int:
        ...

    def __rand__(self, n: int) -> int:
        ...

    def __ror__(self, n: int) -> int:
        ...

    def __rxor__(self, n: int) -> int:
        ...

    def __rlshift__(self, n: int) -> int:
        ...

    def __rrshift__(self, n: int) -> int:
        ...

    def __neg__(self) -> int:
        ...

    def __pos__(self) -> int:
        ...

    def __invert__(self) -> int:
        ...

    def __trunc__(self) -> int:
        ...

    if sys.version_info >= (3, ):

        def __ceil__(self) -> int:
            ...

        def __floor__(self) -> int:
            ...

        def __round__(self, ndigits: Optional[int] = ...) -> int:
            ...

    def __getnewargs__(self) -> Tuple[int]:
        ...

    def __eq__(self, x: object) -> bool:
        ...

    def __ne__(self, x: object) -> bool:
        ...

    def __lt__(self, x: int) -> bool:
        ...

    def __le__(self, x: int) -> bool:
        ...

    def __gt__(self, x: int) -> bool:
        ...

    def __ge__(self, x: int) -> bool:
        ...

    def __str__(self) -> str:
        ...

    def __float__(self) -> float:
        ...

    def __int__(self) -> int:
        ...

    def __abs__(self) -> int:
        ...

    def __hash__(self) -> int:
        ...

    if sys.version_info >= (3, ):

        def __bool__(self) -> bool:
            ...
    else:

        def __nonzero__(self) -> bool:
            ...

    def __index__(self) -> int:
        ...
