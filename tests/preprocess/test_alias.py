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

    A_temp = manager.eval_expr(symid, 'A').temp
    B_temp = manager.eval_expr(symid, 'B').temp
    C_temp = manager.eval_expr(symid, 'B.C').temp

    for temp in [A_temp, B_temp, C_temp]:
        assert isinstance(temp, TypeClassTemp)

    Aalias = manager.eval_expr(symid, 'Aalias')
    Balias = manager.eval_expr(symid, 'Balias')
    Calias = manager.eval_expr(symid, 'Calias')
    UAB = manager.eval_expr(symid, 'UAB')
    OA = manager.eval_expr(symid, 'OA')
    A_ext = manager.eval_expr(symid, 'A_ext')

    for alias in [Aalias, Balias, Calias, UAB, OA, A_ext]:
        assert isinstance(alias, TypeAlias)

    a = manager.eval_expr(symid, 'a')
    b = manager.eval_expr(symid, 'b')
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

    UD = manager.eval_expr(symid, 'UD')
    assert not isinstance(UD, TypeAlias)
