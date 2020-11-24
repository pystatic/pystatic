Any = object()


class TypeVar:
    __name__: str
    __bound__: Optional[Type[Any]]
    __constraints__: Tuple[Type[Any], ...]
    __covariant__: bool
    __contravariant__: bool

    def __init__(
        self,
        name: str,
        *constraints: Type[Any],
        bound: Union[None, Type[Any], str] = ...,
        covariant: bool = ...,
        contravariant: bool = ...,
    ) -> None:
        ...


class _SpecialForm:
    def __getitem__(self, typeargs: Any) -> object:
        ...


Union: _SpecialForm = ...
Optional: _SpecialForm = ...
Tuple: _SpecialForm = ...
Generic: _SpecialForm = ...
# Protocol is only present in 3.8 and later, but mypy needs it unconditionally
Protocol: _SpecialForm = ...
Callable: _SpecialForm = ...
Type: _SpecialForm = ...
ClassVar: _SpecialForm = ...

# Return type that indicates a function does not return.
# This type is equivalent to the None type, but the no-op Union is necessary to
# distinguish the None type from the None value.
NoReturn = Union[None]

# These type variables are used by the container types.
_T = TypeVar("_T")
_S = TypeVar("_S")
_KT = TypeVar("_KT")  # Key type.
_VT = TypeVar("_VT")  # Value type.
_T_co = TypeVar("_T_co", covariant=True)  # Any type covariant containers.
_V_co = TypeVar("_V_co", covariant=True)  # Any type covariant containers.
_KT_co = TypeVar("_KT_co", covariant=True)  # Key type covariant containers.
_VT_co = TypeVar("_VT_co", covariant=True)  # Value type covariant containers.
_T_contra = TypeVar("_T_contra", contravariant=True)  # Ditto contravariant.
_TC = TypeVar("_TC", bound=Type[object])
_C = TypeVar("_C", bound=Callable[..., Any])

no_type_check = object()


def no_type_check_decorator(decorator: _C) -> _C:
    ...


# Type aliases and type constructors


class _Alias:
    # Class for defining generic aliases for library types.
    def __getitem__(self, typeargs: Any) -> Any:
        ...


List = _Alias()
Dict = _Alias()
DefaultDict = _Alias()
Set = _Alias()
FrozenSet = _Alias()
Counter = _Alias()
Deque = _Alias()
ChainMap = _Alias()
OrderedDict = _Alias()

# Predefined type variables.
AnyStr = TypeVar("AnyStr", str, bytes)

Text = str
TYPE_CHECKING = True

# Abstract base classes.


def runtime_checkable(cls: _TC) -> _TC:
    ...

# @runtime_checkable
# class Iterable(Protocol[_T_co]):
#     @abstractmethod
#     def __iter__(self) -> Iterator[_T_co]: ...

# @runtime_checkable
# class Iterator(Iterable[_T_co], Protocol[_T_co]):
#     @abstractmethod
#     def __next__(self) -> _T_co: ...
#     def __iter__(self) -> Iterator[_T_co]: ...
