import ast
import builtins
import enum
from typing import Callable, Tuple, Optional, Type, TypeVar, Union, Dict
from pystatic.typesys import TypeIns, TypeTemp, TypeClassTemp
from pystatic.predefined import (TypeLiteralIns, int_temp, str_temp,
                                 float_temp, bool_temp, complex_temp,
                                 byte_temp)


class Literal2Type:
    def __init__(self):
        self.dict = {
            'int': int_temp,
            'str': str_temp,
            'float': float_temp,
            'bool': bool_temp,
            'complex': complex_temp,
            'byte': byte_temp
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
