from typing import TYPE_CHECKING
import enum


# Enum constant part
class Reach(enum.Enum):
    TYPE_TRUE = 1  # true on type checking(see TYPE_CHECKING)
    TYPE_FALSE = 2  # false on type checking
    RUNTIME_TRUE = 3  # true on runtime
    RUNTIME_FALSE = 4  # false on runtime
    ALWAYS_TRUE = 5  # always true
    ALWAYS_FALSE = 6  # always wrong
    CLS_REDEF = 7  # class redefined(usually omit this)
    NEVER = 8  # node that will never be visited
    UNKNOWN = 9  # uncertain about its reachability



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
