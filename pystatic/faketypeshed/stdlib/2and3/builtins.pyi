from typing import (Optional, Literal, Any, TypeVar, Protocol, Union, Tuple,
                    overload, Dict, Text, Type)


class _SupportsIndex(Protocol):
    def __index__(self) -> int:
        ...


class _SupportsLessThan(Protocol):
    def __lt__(self, __other: Any) -> bool:
        ...


_T = TypeVar("_T")
# _T_co = TypeVar("_T_co", covariant=True)
# _KT = TypeVar("_KT")
# _VT = TypeVar("_VT")
# _S = TypeVar("_S")
# _T1 = TypeVar("_T1")
# _T2 = TypeVar("_T2")
# _T3 = TypeVar("_T3")
# _T4 = TypeVar("_T4")
# _T5 = TypeVar("_T5")
_TT = TypeVar("_TT", bound="object")
# _LT = TypeVar("_LT", bound=_SupportsLessThan)
# _TBE = TypeVar("_TBE", bound="BaseException")


class object:
    __doc__: Optional[str]
    __dict__: Dict[str, Any]
    # __slots__: Union[Text, Iterable[Text]]
    __module__: str
    __annotations__: Dict[str, Any]

    @property
    def __class__(self: _T) -> Type[_T]:
        ...

    @__class__.setter
    def __class__(self, __type: Type[object]) -> None:
        ...  # noqa: F811

    def __init__(self) -> None:
        ...

    def __new__(cls) -> Any:
        ...

    def __setattr__(self, name: str, value: Any) -> None:
        ...

    def __eq__(self, o: object) -> bool:
        ...

    def __ne__(self, o: object) -> bool:
        ...

    def __str__(self) -> str:
        ...

    def __repr__(self) -> str:
        ...

    def __hash__(self) -> int:
        ...

    def __format__(self, format_spec: str) -> str:
        ...

    def __getattribute__(self, name: str) -> Any:
        ...

    def __delattr__(self, name: str) -> None:
        ...

    def __sizeof__(self) -> int:
        ...

    def __reduce__(self) -> Union[str, Tuple[Any, ...]]:
        ...

    def __reduce_ex__(self, protocol: int) -> Union[str, Tuple[Any, ...]]:
        ...

    # def __dir__(self) -> Iterable[str]:
    #     ...

    def __init_subclass__(cls) -> None:
        ...


class int:
    # @overload
    # def __init__(
    #         self,
    #         x: Union[Text, bytes, SupportsInt, _SupportsIndex] = ...) -> None:
    #     ...

    # @overload
    # def __init__(self, x: Union[Text, bytes, bytearray], base: int) -> None:
    #     ...

    # if sys.version_info >= (3, 8):

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

    def to_bytes(self,
                    length: int,
                    byteorder: str,
                    *,
                    signed: bool = ...) -> bytes:
        ...

    # @classmethod
    # def from_bytes(cls,
    #                bytes: Union[Iterable[int], SupportsBytes],
    #                byteorder: str,
    #                *,
    #                signed: bool = ...) -> int:
    #     ...  # TODO buffer object argument

    def __add__(self, x: int) -> int:
        ...

    def __sub__(self, x: int) -> int:
        ...

    def __mul__(self, x: int) -> int:
        ...

    def __floordiv__(self, x: int) -> int:
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

    def __bool__(self) -> bool:
        ...

    def __index__(self) -> int:
        ...


class str:
    pass


class float:
    pass


class complex:
    pass


class bool:
    pass


class bytes:
    pass
