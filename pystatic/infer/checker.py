from pystatic.typesys import *


class TypeChecker:
    def __init__(self, env):
        self.env = env

    def check(self, tp1, tp2, node):
        # TODO: just a temp checker
        if tp1.__str__() == "Any":
            return True
        res = tp1.__str__() == tp2.__str__()
        if not res:
            self.env.add_err(node, f"expected type \'{tp1}\', got \'{tp2}\' instead")

    def check_two_type(self, tp1, tp2):
        if tp1 == tp2:
            return True
        return False
