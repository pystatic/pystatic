import enum


# Enum constant part
class Reach(enum.Enum):
    TYPE_TRUE = 1  # true on type checking(see TYPE_CHECKING)
    TYPE_FALSE = 2  # false on type checking
    ALWAYS_TRUE = 3  # true on runtime
    ALWAYS_FALSE = 4  # false on runtime
    UNKNOWN = 5  # uncertain about its reachability


ACCEPT_REACH = (Reach.ALWAYS_TRUE, Reach.TYPE_TRUE, Reach.UNKNOWN)
REJECT_REACH = (Reach.ALWAYS_FALSE, Reach.TYPE_FALSE)


def cal_neg(res: Reach) -> Reach:
    if res == Reach.TYPE_TRUE:
        return Reach.TYPE_FALSE
    elif res == Reach.TYPE_FALSE:
        return Reach.TYPE_TRUE
    elif res == Reach.ALWAYS_TRUE:
        return Reach.ALWAYS_FALSE
    elif res == Reach.ALWAYS_FALSE:
        return Reach.ALWAYS_TRUE
    else:
        return Reach.UNKNOWN


def is_true(res: Reach, runtime=False) -> bool:
    if runtime:
        return res in (Reach.ALWAYS_TRUE, Reach.TYPE_FALSE)
    else:
        return res in (Reach.ALWAYS_TRUE, Reach.TYPE_TRUE)
