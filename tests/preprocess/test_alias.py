import os
import sys

sys.path.extend(['.', '..'])

from ..util import get_manager_path
from pystatic.typesys import *
from pystatic.predefined import *
from pystatic.config import *
from pystatic.manager import *


def test_alias():
    symid = 'preprocess.prep_alias'
    manager, filepath = get_manager_path({}, symid)
    manager.preprocess()

    module_ins = manager.get_module_ins(symid)
    assert isinstance(module_ins, TypeModuleIns)
    assert module_ins.symid == symid

    A_temp = manager.get_sym_type(symid, 'A').temp
    B_temp = manager.get_sym_type(symid, 'B').temp
    C_temp = manager.get_sym_type(symid, 'B.C').temp

    for temp in [A_temp, B_temp, C_temp]:
        assert isinstance(temp, TypeClassTemp)

    Aalias = manager.get_sym_type(symid, 'Aalias')
    Balias = manager.get_sym_type(symid, 'Balias')
    Calias = manager.get_sym_type(symid, 'Calias')
    UAB = manager.get_sym_type(symid, 'UAB')
    OA = manager.get_sym_type(symid, 'OA')
    A_ext = manager.get_sym_type(symid, 'A_ext')

    for alias in [Aalias, Balias, Calias, UAB, OA, A_ext]:
        assert isinstance(alias, TypeAlias)

    a = manager.get_sym_type(symid, 'a')
    b = manager.get_sym_type(symid, 'b')
    for ins in [a, b]:
        assert not isinstance(ins, TypeAlias)

    aliaes = [Aalias, Balias, Calias, A_ext]
    alias_temps = [A_temp, B_temp, C_temp, A_temp]

    for alias, temp in zip(aliaes, alias_temps):
        assert alias.temp is temp

    assert OA.temp is optional_temp
    assert OA.bindlist
    assert len(OA.bindlist) == 1
    assert OA.bindlist[0].temp is A_temp

    assert UAB.temp is union_temp
    assert UAB.bindlist
    assert len(UAB.bindlist) == 2
    assert UAB.bindlist[0].temp is A_temp
    assert isinstance(UAB.bindlist[0],
                      TypeIns) and not isinstance(UAB.bindlist[0], TypeType)
    assert UAB.bindlist[1].temp is B_temp

    UD = manager.get_sym_type(symid, 'UD')
    assert not isinstance(UD, TypeAlias)
