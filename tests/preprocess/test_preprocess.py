import ast
import sys
import os

sys.path.extend(['.', '..'])

from pystatic.typesys import TypeIns, TypeType
from pystatic.predefined import TypeModuleTemp, TypeFuncIns
from pystatic.config import Config
from pystatic.manager import Manager
from pystatic.exprparse import eval_expr


def parse_expr(expr: str):
    astnode = ast.parse(expr, mode='eval')
    return astnode.body  # type: ignore


def test_preprocess():
    src = 'preprocess1'
    cwd = os.path.dirname(os.path.dirname(__file__))
    config = Config({'cwd': cwd})
    manager = Manager(config)

    filepath = os.path.join(cwd, 'src', 'preprocess', f'{src}.py')
    res_option = manager.add_check_file(filepath)
    assert res_option.value
    manager.preprocess()

    module_temp = manager.get_module_temp(src)
    assert isinstance(module_temp, TypeModuleTemp)
    assert module_temp.module_symid == src

    int_typetype = manager.get_sym_type('builtins', 'int')
    assert int_typetype
    assert isinstance(int_typetype, TypeType)

    A = manager.get_sym_type(src, 'A')
    assert isinstance(A, TypeType)

    a = manager.get_sym_type(src, 'a')
    assert isinstance(a, TypeIns) and not isinstance(a, TypeType)
    assert a.temp == A.temp

    f = manager.get_sym_type(src, 'f')
    assert isinstance(f, TypeFuncIns)

    assert len(f.overloads) == 1
    ret_ins = f.overloads[0].ret_type
    assert isinstance(ret_ins, TypeIns) and not isinstance(ret_ins, TypeType)
    assert ret_ins.temp == A.temp

    assert manager.get_sym_type(src, 'c')
    assert manager.get_sym_type(src, 'd')

    a_dot_a = manager.get_sym_type(src, 'a.a')
    assert isinstance(a_dot_a, TypeIns) and not isinstance(a_dot_a, TypeType)
    assert a_dot_a.temp == int_typetype.temp


def test_import():
    src = 'preprocess_import'
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
