from pystatic.typesys import *


class TypeChecker:
    # TODO: just a temp checker
    def __init__(self, mbox):
        self.mbox = mbox

    def check(self, tp1, tp2):
        if tp1.__str__ == "Any":
            return True
        res = tp1.__str__ == tp2.__str__
        return res

def is_any(tp):
    return tp.__str__ == "Any"
