import ast
import sys
import os

sys.path.extend(['.', '..'])

from pystatic.typesys import ModuleNamedTypeTemp, TypeType, TypeIns, any_ins
from pystatic.predefined import TypeVarIns
from pystatic.predefined import list_type


def test_eq():
    int_temp = ModuleNamedTypeTemp('int', 'builtins')
    float_temp = ModuleNamedTypeTemp('float', 'builtins')
    container_temp = ModuleNamedTypeTemp('container', 'builtins')
    T = TypeVarIns('T', bound=any_ins)
    F = TypeVarIns('F', bound=any_ins)
    container_temp.placeholders = [T, F]

    int_ins1 = int_temp.getins(None).value
    int_ins2 = int_temp.getins([]).value
    assert int_ins1.equiv(int_ins2)

    float_ins1 = float_temp.getins(None).value
    assert not float_ins1.equiv(int_ins1)

    c1 = container_temp.getins([int_ins1, int_ins2]).value
    c2 = container_temp.getins([int_ins2, int_ins1]).value
    c3 = container_temp.getins([float_ins1, int_ins2]).value
    assert c1.equiv(c2)
    assert not c1.equiv(c3)
    assert not c2.equiv(c3)

    c4 = container_temp.getins(None).value
    c5 = container_temp.getins([any_ins, any_ins]).value
    assert c4.equiv(c5)
