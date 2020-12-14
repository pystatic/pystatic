import sys

sys.path.extend(['.', '..'])

from ..util import get_manager_path

from pystatic.typesys import TypeIns, TypeType
from pystatic.predefined import TypeModuleIns, TypeModuleTemp, TypeFuncIns


def test_synthesis_1():
    symid = 'preprocess.prep_1'
    manager, filepath = get_manager_path({}, symid)
    manager.preprocess()

    module_ins = manager.get_module_ins(symid)
    assert isinstance(module_ins, TypeModuleIns)
    assert module_ins.symid == symid

    int_typetype = manager.eval_expr('builtins', 'int')
    assert int_typetype
    assert isinstance(int_typetype, TypeType)

    A = manager.eval_expr(symid, 'A')
    assert isinstance(A, TypeType)

    AB = manager.eval_expr(symid, 'A.B')
    assert isinstance(AB, TypeType)

    a = manager.eval_expr(symid, 'a')
    assert isinstance(a, TypeIns) and not isinstance(a, TypeType)
    assert a.temp == A.temp

    f = manager.eval_expr(symid, 'f')
    assert isinstance(f, TypeFuncIns)

    assert len(f.overloads) == 1
    ret_ins = f.overloads[0].ret_type
    assert isinstance(ret_ins, TypeIns) and not isinstance(ret_ins, TypeType)
    assert ret_ins.temp == A.temp

    assert manager.eval_expr(symid, 'c')
    assert manager.eval_expr(symid, 'd')

    a_dot_a = manager.eval_expr(symid, 'a.a')
    assert isinstance(a_dot_a, TypeIns) and not isinstance(a_dot_a, TypeType)
    assert a_dot_a.temp == int_typetype.temp

    e = manager.eval_expr(symid, 'e')
    assert type(e) == TypeIns
    assert e.temp == A.temp

    g = manager.eval_expr(symid, 'g')
    assert type(g) == TypeIns
    assert g.temp == AB.temp
