from typing import Generic, TypeVar, Any

T = TypeVar('T', bound=Any)


class Option(Generic[T]):
    __slots__ = ['tag', 'value']

    def __init__(self, tag: bool, value: T):
        self.tag = tag
        self.value: T = value
