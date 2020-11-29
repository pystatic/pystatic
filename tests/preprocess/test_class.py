import os
import sys

sys.path.extend(['.', '..'])

from ..util import get_manager_path

from pystatic.typesys import TypeAnyTemp, TypeIns, TypeType
from pystatic.predefined import TypeModuleIns, TypeFuncIns
from pystatic.config import Config
from pystatic.manager import Manager


def test_class():
    symid = 'preprocess.prep_cls'
    manager, file_path = get_manager_path({}, symid)
    manager.preprocess()

    module_ins = manager.get_module_ins(symid)
    assert isinstance(module_ins, TypeModuleIns)
    assert module_ins.symid == symid

    int_typetype = manager.get_sym_type('builtins', 'int')
    assert int_typetype
    assert isinstance(int_typetype, TypeType)

    any_typetype = manager.get_sym_type('typing', 'Any')
    assert any_typetype
    assert isinstance(any_typetype, TypeType)

    A_type = manager.get_sym_type(symid, 'A')
    assert A_type
    static_foo = A_type.getattribute('static_foo', None).value
    assert isinstance(static_foo, TypeFuncIns)  # static method

    static_foo1 = static_foo.overloads[0]
    assert static_foo1.argument.args[0].ann.temp == any_typetype.temp
    assert static_foo1.argument.args[1].ann.temp == int_typetype.temp
    assert static_foo1.ret_type.temp == int_typetype.temp

    cls_foo = A_type.getattribute('class_foo', None).value
    assert isinstance(cls_foo, TypeFuncIns)

    cls_foo1 = cls_foo.overloads[0]
    cls_arg = cls_foo1.argument.args[0].ann
    assert isinstance(
        cls_arg,
        TypeType)  # classmethod's first argument should be the class itself
    assert cls_arg.temp == A_type.temp
    assert cls_foo1.ret_type.temp == any_typetype.temp

    self_foo = A_type.getattribute('__init__', None).value
    assert isinstance(self_foo, TypeFuncIns)

    self_foo1 = self_foo.overloads[0]
    self_arg = self_foo1.argument.args[0].ann
    assert isinstance(self_arg, TypeIns) and not isinstance(
        self_arg, TypeType
    )  # normal method's first argument should be the instance of the Type
    assert self_foo1.argument.args[0].ann.temp == A_type.temp
