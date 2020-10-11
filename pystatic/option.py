from typing import Generic, Optional, TypeVar, Any
from pystatic.errorcode import ErrorCode

T = TypeVar('T', bound=Any)


class Option(Generic[T]):
    __slots__ = ['errors', 'value']

    def __init__(self, default: T):
        self.value: T = default
        self.errors = None

    def add_error(self, error: ErrorCode):
        if not self.errors:
            self.errors = []
        self.errors.append(error)

    def set_value(self, value: T):
        self.value = value
