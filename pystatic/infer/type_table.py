from enum import Enum
from pystatic.typesys import *


class NodeType(Enum):
    CLASS_TYPE = 0
    VAR_TYPE = 1


class Symbol:
    def __init__(self, name: str, tp: TypeIns):
        self.name = name
        self.tp = tp
        self.child: Dict[str, TypeIns] = {}


class VarTree:
    def __init__(self):
        self.child: Dict[str, Symbol] = {}
        self.cls: Dict[str, Symbol] = {}
        self.func: Dict[str, Symbol] = {}

    def add_var(self, name, tp):
        self.child[name] = Symbol(name, tp)

    def add_cls(self, name, tp):
        self.cls[name] = Symbol(name, tp)

    def add_func(self, name, tp):
        self.func[name] = Symbol(name, tp)

    def lookup_var(self, name):
        symb = self.child.get(name)
        if symb is not None:
            return symb.tp
        else:
            return None

    def lookup_cls(self, name):
        symb = self.cls.get(name)
        if symb is not None:
            return symb.tp
        else:
            return None

    def lookup_func(self, name):
        symb = self.func.get(name)
        if symb is not None:
            return symb.tp
        else:
            return None
