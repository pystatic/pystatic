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
