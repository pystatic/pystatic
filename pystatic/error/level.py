import enum


class Level(enum.Enum):
    HINT = 1  # code unreachable
    WARN = 2  # type error
    ERROR = 3  # will cause runtime error
