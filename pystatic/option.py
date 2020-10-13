from typing import Generic, Optional, TypeVar, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from pystatic.errorcode import ErrorCode

T = TypeVar('T', bound=Any, covariant=True)


class Option(Generic[T]):
    __slots__ = ['errors', 'value']

    def __init__(self, default):
        self.value: T = default
        self.errors = None

    def add_err(self, error: 'ErrorCode'):
        if not self.errors:
            self.errors = []
        self.errors.append(error)

    def set_value(self, value):
        self.value = value
