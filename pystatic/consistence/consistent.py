from pystatic.typesys import TypeClassTemp, INFINITE_ARITY
from pystatic.predefined import *


def is_consistent(left_ins: "TypeIns", right_ins: "TypeIns"):
    """Is "a = b" safe or not"""
    # TODO: protocol
    if left_ins == any_ins or right_ins == any_ins:
        return True

    is_left_classins = isinstance(left_ins.temp, TypeClassTemp)
    is_right_classins = isinstance(right_ins.temp, TypeClassTemp)

    if is_left_classins and is_right_classins:
        return cls_consistent(right_ins, left_ins)

    # one of left_ins and right_ins is special types
    if left_ins == right_ins == none_ins:
        return True
    elif left_ins == none_ins or right_ins == none_ins:
        return False

    if is_left_classins:
        # left instance's type is normal class-defined type
        if right_ins.temp == union_temp:
            for union_ins in right_ins.bindlist:
                if not is_consistent(left_ins, union_ins):
                    return False
            return True
        elif right_ins.temp == optional_temp:
            return False  # left can't be None
        elif right_ins.temp == literal_temp:
            assert isinstance(right_ins, TypeLiteralIns)
            return is_consistent(left_ins, right_ins.get_value_type())
    else:
        if left_ins.temp == union_temp:
            for union_ins in left_ins.bindlist:
                if is_consistent(union_ins, right_ins):
                    return True
            return False
        elif left_ins.temp == optional_temp:
            if is_consistent(left_ins.get_safe_bind(0), right_ins):
                return True
            return right_ins == none_ins
        elif left_ins.temp == literal_temp:
            assert isinstance(left_ins, TypeLiteralIns)
            assert isinstance(right_ins, TypeLiteralIns)
            return right_ins.temp == literal_temp and left_ins.value == right_ins.value

    return left_ins.equiv(right_ins)


def cls_consistent(left_ins: "TypeIns", right_ins: "TypeIns"):
    if left_ins.temp != right_ins.temp:
        left_mro = left_ins.temp.get_mro()
        for inh in left_mro:
            if inh.temp == right_ins.temp:
                return cls_consistent(inh, right_ins)
        return False
    else:
        arity = left_ins.temp.arity()
        if arity == INFINITE_ARITY:
            # Tuple like classes
            left_len = len(left_ins.bindlist)
            if left_len != len(right_ins.bindlist):
                return False
            else:
                fst_tpvar = left_ins.temp.placeholders[0]
                assert isinstance
                for left, right in zip(left_ins.bindlist, right_ins.bindlist):
                    if not consistent_with_tpvar(left, right, fst_tpvar):
                        return False
        else:
            assert len(left_ins.temp.placeholders) == arity
            temp = left_ins.temp

            for i in range(arity):
                tpvar = temp.placeholders[i]
                left = left_ins.get_safe_bind(i)
                right = right_ins.get_safe_bind(i)
                if not consistent_with_tpvar(left, right, tpvar):
                    return False
        return True


def consistent_with_tpvar(
    left_ins: "TypeIns", right_ins: "TypeIns", tpvar: "TypeVarIns"
):
    if tpvar.kind == INVARIANT:
        if not left_ins.equiv(right_ins):
            return False
    elif tpvar.kind == COVARIANT:
        if not cls_consistent(left_ins, right_ins):
            return False
    elif tpvar.kind == CONTRAVARIANT:
        if not cls_consistent(right_ins, left_ins):
            return False
    else:
        raise ValueError()
    return True