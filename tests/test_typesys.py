import ast
import sys
import os

sys.path.extend(['.', '..'])

from pystatic.typesys import TypeTemp, TypeType, TypeIns, TypeVarIns, list_type, any_ins


def test_eq():
    int_temp = TypeTemp('int', 'builtins')
    float_temp = TypeTemp('float', 'builtins')
    container_temp = TypeTemp('container', 'builtins')
    T = TypeVarIns('T', bound=any_ins)
    F = TypeVarIns('F', bound=any_ins)
    container_temp.placeholders = [T, F]

    int_ins1 = int_temp.getins(None).value
    int_ins2 = int_temp.getins([]).value
    assert int_ins1 == int_ins2

    float_ins1 = float_temp.getins(None).value
    assert float_ins1 != int_ins1

    c1 = container_temp.getins([int_ins1, int_ins2]).value
    c2 = container_temp.getins([int_ins2, int_ins1]).value
    c3 = container_temp.getins([float_ins1, int_ins2]).value
    assert c1 == c2
    assert c1 != c3
    assert c2 != c3

    c4 = container_temp.getins(None).value
    c5 = container_temp.getins([any_ins, any_ins]).value
    assert c4 == c5
