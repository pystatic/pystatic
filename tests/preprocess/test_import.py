import sys
import os

sys.path.extend(['.', '..'])
from ..util import get_manager_path

from pystatic.typesys import TypeIns, TypeType
from pystatic.predefined import TypeModuleTemp, TypeFuncIns, TypeVarIns
from pystatic.config import Config
from pystatic.manager import Manager
from pystatic.typesys import TypeIns, TypeType
from pystatic.predefined import TypeModuleTemp, TypeFuncIns, TypeVarIns
from pystatic.config import Config
from pystatic.manager import Manager


def test_import():
    symid = 'preprocess.prep_import'
    manager, filepath = get_manager_path({}, symid)
    manager.preprocess()

    module_temp = manager.get_module_temp(symid)
    assert isinstance(module_temp, TypeModuleTemp)
    assert module_temp.module_symid == symid

    banana = manager.get_sym_type(symid, 'banana')
    Banana = manager.get_sym_type(symid, 'Banana')
    assert isinstance(banana, TypeIns)
    assert isinstance(Banana, TypeType)
    assert banana.temp == Banana.temp

    love_fruit = manager.eval_expr(symid, 'love_banana(banana)')
    assert isinstance(love_fruit, TypeIns)
    assert love_fruit.temp == Banana.temp

def test_star_import():
    symid = 'preprocess.star_import'
    manager, filepath = get_manager_path({}, symid)
    manager.preprocess()

    module_temp = manager.get_module_temp(symid)
    assert isinstance(module_temp, TypeModuleTemp)
    assert module_temp.module_symid == symid
    
    a = manager.get_sym_type(symid, 'a')
    pack_type = manager.get_sym_type(symid, 'Pack')
    assert isinstance(a, TypeIns) and not isinstance(a, TypeType)
    assert isinstance(pack_type, TypeType)
    assert a.temp == pack_type.temp
