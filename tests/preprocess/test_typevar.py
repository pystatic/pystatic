import sys
import os

sys.path.extend([".", ".."])
from ..util import get_manager_path

from pystatic.typesys import *
from pystatic.predefined import *
from pystatic.config import Config
from pystatic.manager import Manager


def test_typevar():
    symid = "preprocess.prep_typevar"
    manager, filepath = get_manager_path({}, symid)
    manager.preprocess()

    module_ins = manager.get_module_ins(symid)
    assert isinstance(module_ins, TypeModuleIns)
    assert module_ins.symid == symid

    int_typetype = manager.eval_expr("builtins", "int")
    int_ins = int_typetype.temp.get_default_ins().value
    assert isinstance(int_typetype, TypeType)
    assert isinstance(int_ins, TypeIns)

    str_typetype = manager.eval_expr("builtins", "str")
    str_ins = str_typetype.temp.get_default_ins().value
    assert isinstance(str_typetype, TypeType)
    assert isinstance(str_ins, TypeIns)

    T = manager.eval_expr(symid, "T")
    F = manager.eval_expr(symid, "F")
    G = manager.eval_expr(symid, "G")
    H = manager.eval_expr(symid, "H")
    A = manager.eval_expr(symid, "A")
    B = manager.eval_expr(symid, "B")
    I = manager.eval_expr(symid, "I")
    assert isinstance(A, TypeType)
    assert isinstance(B, TypeType)
    assert isinstance(T, TypeVarIns)
    assert isinstance(F, TypeVarIns)
    assert isinstance(G, TypeVarIns)
    assert isinstance(H, TypeVarIns)
    assert isinstance(I, TypeVarIns)

    assert len(F.constraints) == 2
    assert F.constraints[0] is int_ins
    assert F.constraints[1] is str_ins
    assert G.bound is int_ins
    assert H.bound is str_ins
    assert H.kind == COVARIANT
    assert I.kind == INVARIANT
    assert I.bound is int_ins

    A_temp = A.temp
    B_temp = B.temp
    assert len(A_temp.placeholders) == 4
    assert A_temp.placeholders[0] is T
    assert A_temp.placeholders[1] is G
    assert A_temp.placeholders[2] is H
    assert A_temp.placeholders[3] is I
    assert len(B_temp.placeholders) == 1
    assert B_temp.placeholders[0] is F

    assert isinstance(B_temp, TypeClassTemp)
    assert len(B_temp.baseclass) == 1
    assert isinstance(B_temp.baseclass[0], TypeIns) and not isinstance(
        B_temp.baseclass[0], TypeType
    )
    assert B_temp.baseclass[0].temp is A_temp
