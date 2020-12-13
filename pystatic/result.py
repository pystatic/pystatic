from typing import Generic, TypeVar, Any, TYPE_CHECKING, List

if TYPE_CHECKING:
    from pystatic.errorcode import ErrorCode
    from pystatic.message import MessageBox

T = TypeVar('T', bound=Any, covariant=True)


class Result(Generic[T]):
    __slots__ = ['errors', 'value']

    def __init__(self, default):
        self.value: T = default
        self.errors = None

    def add_err(self, error: 'ErrorCode'):
        if not self.errors:
            self.errors = []
        self.errors.append(error)

    def add_err_list(self, errors: List['ErrorCode']):
        if not self.errors:
            self.errors = []
        self.errors.extend(errors)

    def set_value(self, value):
        self.value = value

    def combine_error(self, other: 'Result'):
        if other.errors:
            if not self.errors:
                self.errors = other.errors
            else:
                self.errors.extend(other.errors)

    def dump_to_box(self, mbox: 'MessageBox'):
        if self.errors:
            mbox.error.extend(self.errors)

    def haserr(self):
        if self.errors:
            return len(self.errors) > 0
        return False
