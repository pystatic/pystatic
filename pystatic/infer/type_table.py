import ast
from enum import Enum
from pystatic.typesys import *


class SymbolType(Enum):
    GLOBAL_TYPE = 0
    LOCAL_TYPE = 1
    NON_LOCAL_TYPE = 2
    CLASS_TYPE = 3
    VAR_TYPE = 4


class Symbol:
    def __init__(self, name: str, tp: TypeIns, parent: "Symbol",
                 symbol_type: SymbolType):
        self.name = name
        self.tp = tp
        self.symbol_type = symbol_type
        self.parent = parent

        self.discovered = True
        self.attr: Dict[str, Symbol] = {}

    def add_attr(self, name: str, symbol: "Symbol"):
        self.attr[name] = symbol

    def get_attr(self, name: str):
        return self.tp.getattr(name)

    def set_attr(self, name, tp):
        self.tp.setattr(name, tp)

    def get_cls(self, name):
        symbol = self.attr.get(name)
        assert symbol is not None
        assert symbol.symbol_type == SymbolType.CLASS_TYPE
        return symbol

    def get_func(self, name):
        symbol = self.attr.get(name)
        assert symbol is not None
        assert symbol.symbol_type == SymbolType.LOCAL_TYPE or \
               symbol.symbol_type == SymbolType.NON_LOCAL_TYPE
        return symbol

    def is_defined(self, name) -> bool:
        return name in self.attr


class VarTree:
    def __init__(self, module: TypeModuleTemp):
        self.root = Symbol(module.name, module, None, SymbolType.GLOBAL_TYPE)
        self.cur_symbol: Symbol = self.root
        self.in_func = False

    def add_cls(self, name, tp):
        symbol = Symbol(name, tp, self.cur_symbol, SymbolType.CLASS_TYPE)
        self.cur_symbol.add_attr(name, symbol)

    def add_var(self, name, tp):
        symbol = Symbol(name, tp, self.cur_symbol, SymbolType.VAR_TYPE)
        self.cur_symbol.add_attr(name, symbol)
        self.cur_symbol.set_attr(name, tp)

    def add_func(self, name, tp):
        if self.in_func:
            symbol = Symbol(name, tp, self.cur_symbol, SymbolType.NON_LOCAL_TYPE)
        else:
            symbol = Symbol(name, tp, self.cur_symbol, SymbolType.LOCAL_TYPE)
        self.cur_symbol.add_attr(name, symbol)

    def enter_cls(self, name):
        self.cur_symbol = self.cur_symbol.get_cls(name)

    def leave_cls(self):
        self.cur_symbol = self.cur_symbol.parent

    def enter_func(self, name):
        self.cur_symbol = self.cur_symbol.get_func(name)

    def leave_func(self):
        self.leave_cls()

    def lookup_attr(self, name):
        return self.cur_symbol.get_attr(name)

    def is_defined(self, name):
        return self.cur_symbol.is_defined(name)
