import sys
import os

sys.path.extend(['.', '..'])

from pystatic.typesys import TypeIns, TypeType
from pystatic.predefined import TypeModuleTemp, TypeFuncIns, TypeVarIns
from pystatic.config import Config
from pystatic.manager import Manager
from pystatic.typesys import TypeIns, TypeType
from pystatic.predefined import TypeModuleTemp, TypeFuncIns, TypeVarIns
from pystatic.config import Config
from pystatic.manager import Manager
from pystatic.exprparse import eval_expr


def test_import():
    src = 'prep_import'
    cwd = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src',
                       'preprocess')  # tests/src/preprocess/preprocess_import
    config = Config({'cwd': cwd, 'no_typeshed': True})
    manager = Manager(config)

    filepath = os.path.join(cwd, f'{src}.py')
    res_option = manager.add_check_file(filepath)
    assert res_option.value
    manager.preprocess()

    module_temp = manager.get_module_temp(src)
    assert isinstance(module_temp, TypeModuleTemp)
    assert module_temp.module_symid == src

    banana = manager.get_sym_type(src, 'banana')
    Banana = manager.get_sym_type(src, 'Banana')
    assert isinstance(banana, TypeIns)
    assert isinstance(Banana, TypeType)
    assert banana.temp == Banana.temp

    love_fruit = manager.eval_expr(src, 'love_banana(banana)')
    assert isinstance(love_fruit, TypeIns)
    assert love_fruit.temp == Banana.temp
