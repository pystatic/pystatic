import sys
import os

sys.path.extend(['.', '..'])
from ..util import get_manager_path

from pystatic.typesys import TypeIns, TypeType
from pystatic.predefined import TypeModuleIns, TypeModuleTemp, TypeFuncIns, TypeVarIns
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

    module_ins = manager.get_module_ins(symid)
    assert isinstance(module_ins, TypeModuleIns)
    assert module_ins.symid == symid

    banana = manager.eval_expr(symid, 'banana')
    Banana = manager.eval_expr(symid, 'Banana')
    vegetable = manager.eval_expr(symid, 'vegetable')
    c = manager.eval_expr(symid, 'c')
    assert isinstance(banana, TypeIns)
    assert isinstance(Banana, TypeType)
    assert isinstance(c, TypeIns) and not isinstance(c, TypeType)
    assert banana.temp == Banana.temp

    love_fruit = manager.eval_expr(symid, 'love_banana(banana)')
    assert isinstance(love_fruit, TypeIns)
    assert love_fruit.temp == Banana.temp


def test_star_import():
    symid = 'preprocess.star_import'
    manager, filepath = get_manager_path({}, symid)
    manager.preprocess()

    module_ins = manager.get_module_ins(symid)
    assert isinstance(module_ins, TypeModuleIns)
    assert module_ins.symid == symid

    a = manager.eval_expr(symid, 'a')
    pack_type = manager.eval_expr(symid, 'Pack')
    assert isinstance(a, TypeIns) and not isinstance(a, TypeType)
    assert isinstance(pack_type, TypeType)
    assert a.temp == pack_type.temp
