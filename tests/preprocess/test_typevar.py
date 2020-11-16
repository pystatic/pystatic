import sys
import os
import ast

sys.path.extend(['.', '..'])

from pystatic.typesys import TypeIns, TypeType
from pystatic.predefined import TypeModuleTemp, TypeFuncIns, TypeVarIns
from pystatic.config import Config
from pystatic.manager import Manager
from pystatic.exprparse import eval_expr


def test_typevar():
    src = 'prep_typevar'
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

    str_typetype = manager.get_sym_type('builtins', 'str')
    assert str_typetype
    assert isinstance(str_typetype, TypeType)

    T = manager.get_sym_type(src, 'T')
    F = manager.get_sym_type(src, 'F')
    A = manager.get_sym_type(src, 'A')
    B = manager.get_sym_type(src, 'B')
    assert isinstance(A, TypeType)
    assert isinstance(B, TypeType)
    assert isinstance(T, TypeVarIns)
    assert isinstance(F, TypeVarIns)
