from pystatic.typesys import TypeClassTemp
from pystatic.predefined import *


def is_subclass(subcls: "TypeIns", pacls: "TypeIns"):
    subtemp = subcls.temp
    patemp = pacls.temp
    sub_mro = subtemp.get_mro()
    return patemp in sub_mro


def is_consistent(left_ins: "TypeIns", right_ins: "TypeIns"):
    """Is "a = b" safe or not"""
    # TODO: protocol
    if left_ins == any_ins or right_ins == any_ins:
        return True

    is_left_classins = isinstance(left_ins.temp, TypeClassTemp)
    is_right_classins = isinstance(right_ins.temp, TypeClassTemp)

    if is_left_classins and is_right_classins:
        return is_subclass(right_ins, left_ins)

    if left_ins == right_ins == none_ins:
        return True
    elif left_ins == none_ins or right_ins == none_ins:
        return False

    if left_ins.temp == union_temp:
        for union_ins in left_ins.bindlist:
            if is_consistent(union_ins, right_ins):
                return True
        return False
    elif left_ins.temp == optional_temp:
        if is_consistent(left_ins.get_safe_bind(0), right_ins):
            return True
        return right_ins == none_ins

    return left_ins.equiv(right_ins)
