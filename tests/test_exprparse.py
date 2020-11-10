import ast
import sys
import os

sys.path.extend(['.', '..'])

from pystatic.typesys import TypeIns, TypeType
from pystatic.predefined import TypeModuleTemp
from pystatic.config import Config
from pystatic.manager import Manager
from pystatic.exprparse import eval_expr


def parse_expr(expr: str):
    astnode = ast.parse(expr, mode='eval')
    return astnode.body  # type: ignore


def test_exprparse():
    src = 'exprparse1'
    cwd = os.path.dirname(__file__)
    config = Config({'cwd': cwd})
    manager = Manager(config)
    file_path = os.path.join(cwd, 'src', f'{src}.py')
    res_option = manager.add_check_file(file_path)
    assert res_option.value
    manager.preprocess()

    module_temp = manager.get_module_temp(src)
    assert isinstance(module_temp, TypeModuleTemp)
    assert module_temp.module_symid == src
    module_ins = module_temp.get_default_ins().value

    int_typetype = manager.get_sym_type('builtins', 'int')
    assert int_typetype
    assert isinstance(int_typetype, TypeType)

    a = manager.get_sym_type(src, 'a')
    assert a
    assert a.temp == int_typetype.temp

    c = manager.get_sym_type(src, 'c')
    d = manager.get_sym_type(src, 'd')
    A = manager.get_sym_type(src, 'A')
    B = manager.get_sym_type(src, 'B')

    assert isinstance(c, TypeIns)
    assert isinstance(d, TypeIns)
    assert isinstance(A, TypeType)
    assert isinstance(B, TypeType)
    assert c.temp == A.temp
    assert d.temp == B.temp

    # test '__add__'
    astnode = parse_expr('c + d')
    eval_option = eval_expr(astnode, module_ins)
    assert not eval_option.haserr()
    eval_res = eval_option.value
    assert isinstance(eval_res, TypeIns)
    assert eval_res.temp == B.temp
