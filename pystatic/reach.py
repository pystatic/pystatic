from typing import TYPE_CHECKING
import enum


# Enum constant part
class Reach(enum.Enum):
    TYPE_TRUE = 1
    TYPE_FALSE = 2
    RUNTIME_TRUE = 3
    RUNTIME_FALSE = 4
    ALWAYS_TRUE = 5
    ALWAYS_FALSE = 6
    CLS_REDEF = 7
    NEVER = 8
    UNKNOWN = 9


def cal_neg(res: Reach) -> Reach:
    if res == Reach.TYPE_TRUE:
        return Reach.TYPE_FALSE
    elif res == Reach.TYPE_FALSE:
        return Reach.TYPE_TRUE
    elif res == Reach.RUNTIME_TRUE:
        return Reach.RUNTIME_FALSE
    elif res == Reach.RUNTIME_FALSE:
        return Reach.RUNTIME_TRUE
    elif res == Reach.ALWAYS_FALSE:
        return Reach.ALWAYS_TRUE
    elif res == Reach.ALWAYS_TRUE:
        return Reach.ALWAYS_FALSE
    else:
        return Reach.UNKNOWN


def is_true(res: Reach, runtime=False) -> bool:
    if runtime:
        return res in (Reach.ALWAYS_TRUE, Reach.RUNTIME_TRUE)
    else:
        return res in (Reach.ALWAYS_TRUE, Reach.TYPE_TRUE)
