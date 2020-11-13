from typing import Generic, Optional, TypeVar, Any, TYPE_CHECKING, List

if TYPE_CHECKING:
    from pystatic.errorcode import ErrorCode
    from pystatic.message import MessageBox

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

    def add_errlist(self, errors: List['ErrorCode']):
        if not self.errors:
            self.errors = []
        self.errors.extend(errors)

    def set_value(self, value):
        self.value = value

    def combine_error(self, other: 'Option'):
        if other.errors:
            self.add_errlist(other.errors)

    def dump_to_box(self, mbox: 'MessageBox'):
        if self.errors:
            for error in self.errors:
                mbox.add_err(error)

    def haserr(self):
        return self.errors and len(self.errors) > 0
