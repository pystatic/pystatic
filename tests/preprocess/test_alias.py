import os
import sys

sys.path.extend(['.', '..'])

from pystatic.typesys import *
from pystatic.predefined import *
from pystatic.config import *
from pystatic.manager import *


def test_alias():
    symid = 'prep_alias'
    cwd = os.path.dirname(os.path.dirname(__file__))
    config = Config({'cwd': cwd})
    manager = Manager(config)
    file_path = os.path.join(cwd, 'src', 'preprocess', f'{symid}.py')
    res_option = manager.add_check_file(file_path)
    assert res_option.value
    manager.preprocess()

    module_temp = manager.get_module_temp(symid)
    assert isinstance(module_temp, TypeModuleTemp)
    assert module_temp.module_symid == symid

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
