import enum


# Enum constant part
class Reach(enum.Enum):
    TYPE_TRUE = 1  # true on type checking(see TYPE_CHECKING)
    TYPE_FALSE = 2  # false on type checking
    RUNTIME_TRUE = 3  # true on runtime
    RUNTIME_FALSE = 4  # false on runtime
    UNKNOWN = 5  # uncertain about its reachability


ACCEPT_REACH = (Reach.RUNTIME_TRUE, Reach.TYPE_TRUE, Reach.UNKNOWN)
REJECT_REACH = (Reach.RUNTIME_FALSE, Reach.TYPE_FALSE)


def cal_neg(res: Reach) -> Reach:
    if res == Reach.TYPE_TRUE:
        return Reach.TYPE_FALSE
    elif res == Reach.TYPE_FALSE:
        return Reach.TYPE_TRUE
    elif res == Reach.RUNTIME_TRUE:
        return Reach.RUNTIME_FALSE
    elif res == Reach.RUNTIME_FALSE:
        return Reach.RUNTIME_TRUE
    else:
        return Reach.UNKNOWN



