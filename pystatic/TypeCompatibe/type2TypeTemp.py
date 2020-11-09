import ast
import builtins
import enum
from typing import Callable, Tuple, Optional, Type, TypeVar, Union, Dict
from pystatic.typesys import TypeIns, TypeTemp, TypeClassTemp
from pystatic.predefined import (TypeOptionalTemp, TypeTupleTemp, TypeListTemp,
                                 TypeLiteralTemp, TypeLiteralIns)


class Literal2Type:
    def __init__(self):
        self.dict = {
            'int': TypeTemp('int', builtins),
            'str': TypeTemp('str', builtins),
            'float': TypeTemp('float', builtins),
            'bool': TypeTemp('bool', builtins),
            'complex': TypeTemp('complex', builtins),
            'byte': TypeTemp('byte', builtins)
        }

    def Literal2SpecTypeTemp(self, Liter: TypeLiteralIns) -> TypeTemp:
        value = Liter.value
        valueType = type(value)
        typetmp = self.dict[str(valueType)[8:-2]]
        return typetmp

    def Literal2SpecTypeIns(self, Liter: TypeLiteralIns):
        value = Liter.value
        valueType = type(value)
        # print(valueType)
        typetmp = self.dict[str(valueType)[8:-2]]
        typeins = typetmp.get_default_ins().value
        # print("Liter2Ins")
        # print(typeins)
        # print(type(typeins))
        return typeins
