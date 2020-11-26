import sys

sys.path.extend(['.', '..'])

from ..util import get_manager_path

from pystatic.typesys import TypeIns, TypeType
from pystatic.predefined import TypeModuleTemp, TypeFuncIns


def test_synthesis_1():
    symid = 'preprocess.prep_1'
    manager, filepath = get_manager_path({}, symid)
    manager.preprocess()

    module_temp = manager.get_module_temp(symid)
    assert isinstance(module_temp, TypeModuleTemp)
    assert module_temp.module_symid == symid

    int_typetype = manager.get_sym_type('builtins', 'int')
    assert int_typetype
    assert isinstance(int_typetype, TypeType)

    A = manager.get_sym_type(symid, 'A')
    assert isinstance(A, TypeType)

    AB = manager.get_sym_type(symid, 'A.B')
    assert isinstance(AB, TypeType)

    a = manager.get_sym_type(symid, 'a')
    assert isinstance(a, TypeIns) and not isinstance(a, TypeType)
    assert a.temp == A.temp

    f = manager.get_sym_type(symid, 'f')
    assert isinstance(f, TypeFuncIns)

    assert len(f.overloads) == 1
    ret_ins = f.overloads[0].ret_type
    assert isinstance(ret_ins, TypeIns) and not isinstance(ret_ins, TypeType)
    assert ret_ins.temp == A.temp

    assert manager.get_sym_type(symid, 'c')
    assert manager.get_sym_type(symid, 'd')

    a_dot_a = manager.get_sym_type(symid, 'a.a')
    assert isinstance(a_dot_a, TypeIns) and not isinstance(a_dot_a, TypeType)
    assert a_dot_a.temp == int_typetype.temp

    e = manager.get_sym_type(symid, 'e')
    assert type(e) == TypeIns
    assert e.temp == A.temp

    g = manager.get_sym_type(symid, 'g')
    assert type(g) == TypeIns
    assert g.temp == AB.temp
