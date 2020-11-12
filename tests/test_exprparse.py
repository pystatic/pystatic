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
    str_typetype = manager.get_sym_type('builtins', 'str')
    assert str_typetype
    assert isinstance(str_typetype, TypeType)

    a = manager.get_sym_type(src, 'a')
    assert a
    assert a.temp == int_typetype.temp

    c = manager.get_sym_type(src, 'c')
    d = manager.get_sym_type(src, 'd')
    A = manager.get_sym_type(src, 'A')
    B = manager.get_sym_type(src, 'B')

    assert isinstance(c, TypeIns) and not isinstance(c, TypeType)
    assert isinstance(d, TypeIns) and not isinstance(d, TypeType)
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

    # container
    e = manager.get_sym_type(src, 'e')
    assert isinstance(e, TypeIns) and not isinstance(e, TypeType)
    assert e.bindlist
    e_fst = e.bindlist[0]
    assert isinstance(e_fst, TypeIns) and not isinstance(e_fst, TypeType)
    assert e_fst.temp == int_typetype.temp

    f = manager.get_sym_type(src, 'f')
    assert isinstance(f, TypeIns) and not isinstance(f, TypeType)
    assert f.bindlist
    f_fst = f.bindlist[0]
    f_snd = f.bindlist[1]
    assert isinstance(f_fst, TypeIns) and not isinstance(f_fst, TypeType)
    assert isinstance(f_snd, TypeIns) and not isinstance(f_snd, TypeType)
    assert f_fst.temp == str_typetype.temp
    assert f_snd.temp == int_typetype.temp
