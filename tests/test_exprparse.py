import ast
import sys
import os

sys.path.extend([".", ".."])

from pystatic.typesys import TypeIns, TypeType
from pystatic.predefined import *
from pystatic.config import Config
from pystatic.manager import Manager
from pystatic.exprparse import eval_expr
from .util import error_assert

def parse_expr(expr: str):
    astnode = ast.parse(expr, mode="eval")
    return astnode.body  # type: ignore


def parse_eval_check(
    expr: str, module_ins, expect: TypeIns, equiv: bool, explicit=False
):
    astnode = parse_expr(expr)
    eval_option = eval_expr(astnode, module_ins, explicit)
    eval_res = eval_option.value
    if equiv:
        assert eval_res.equiv(expect)
    else:
        assert eval_res is expect


def parse_eval_ann_check(expr: str, module_ins, expect: TypeIns):
    astnode = parse_expr(expr)
    eval_option = eval_expr(astnode, module_ins)
    eval_res = eval_option.value
    assert isinstance(eval_res, TypeType)
    eval_res = eval_res.get_default_ins()
    assert eval_res.equiv(expect)


def test_exprparse_basic():
    cwd = os.path.dirname(__file__)
    manager = Manager(Config({"cwd": cwd}))

    parse_eval_check("1", typing_symtable, TypeLiteralIns(1), True)
    parse_eval_check("'hello'", typing_symtable, TypeLiteralIns("hello"), True)
    parse_eval_check("1 < 2", typing_symtable, bool_ins, False)
    parse_eval_check("[1, 2]", typing_symtable, TypeIns(list_temp, [int_ins]), True)
    parse_eval_check(
        "[1, 'hello']", typing_symtable, TypeIns(list_temp, [any_ins]), True
    )
    parse_eval_check(
        "(1, 2)", typing_symtable, TypeIns(tuple_temp, [int_ins, int_ins]), True
    )
    parse_eval_check(
        "(1, 2)",
        typing_symtable,
        TypeIns(tuple_temp, [TypeLiteralIns(1), TypeLiteralIns(2)]),
        True,
        True,
    )
    parse_eval_check("{1, 2}", typing_symtable, TypeIns(set_temp, [int_ins]), True)
    parse_eval_check(
        '{1: "good", 2: "good"}',
        typing_symtable,
        TypeIns(dict_temp, [int_ins, str_ins]),
        True,
    )

    parse_eval_ann_check("Type[int]", typing_symtable, TypeType(int_temp, None))


def test_exprparse_type_expr():
    src = "exprparse_type_expr"
    cwd = os.path.dirname(__file__)
    config = Config({"cwd": cwd})
    manager = Manager(config)
    file_path = os.path.join(cwd, "src", f"{src}.py")
    result = manager.add_check_file(file_path)
    assert result.value
    manager.preprocess()

    a = manager.eval_expr(src, "a")
    b = manager.eval_expr(src, "b")
    c = manager.eval_expr(src, "c")
    d = manager.eval_expr(src, "d")
    e = manager.eval_expr(src, "e")
    f = manager.eval_expr(src, "f")
    g = manager.eval_expr(src, "g")
    A = manager.eval_expr(src, "A")
    assert isinstance(a, TypeIns) and not isinstance(a, TypeType)
    cur_union = union_temp.get_default_ins().value
    cur_union.bindlist = [int, str]
    cur_optional = optional_temp.get_default_ins().value
    cur_optional.bindlist = [cur_union]
    assert a.equiv(cur_optional)

    assert len(b.bindlist) == 1
    assert isinstance(b.bindlist[0], TypeIns) and not isinstance(
        b.bindlist[0], TypeType
    )
    assert b.bindlist[0].temp is A.temp

    assert len(c.bindlist) == 1
    assert isinstance(c.bindlist[0], TypeType)
    assert c.bindlist[0].temp is A.temp

    assert len(d.bindlist) == 2
    assert d.bindlist[0] is int_ins
    assert d.bindlist[1] is ellipsis_ins

    assert len(f.bindlist) == 1
    assert f.bindlist[0] == "test"

    assert len(g.bindlist) == 2
    assert isinstance(g.bindlist[0], TypeLiteralIns)
    assert g.bindlist[0].value == 1
    assert g.bindlist[1] == int_ins

    assert str(a) == "Optional[Union[int, str]]"
    assert str(b) == "Optional[A]"
    assert str(c) == "Optional[Type[A]]"
    assert str(d) == "Tuple[int, ...]"
    assert str(e) == "Tuple[int, str]"


def test_exprparse1():
    src = "exprparse1"
    cwd = os.path.dirname(__file__)
    config = Config({"cwd": cwd})
    manager = Manager(config)
    file_path = os.path.join(cwd, "src", f"{src}.py")
    result = manager.add_check_file(file_path)
    assert result.value
    manager.preprocess()

    module_ins = manager.get_module_ins(src)
    assert isinstance(module_ins, TypeModuleIns)
    assert module_ins.symid == src

    int_typetype = manager.eval_expr("builtins", "int")
    assert int_typetype
    assert isinstance(int_typetype, TypeType)
    str_typetype = manager.eval_expr("builtins", "str")
    assert str_typetype
    assert isinstance(str_typetype, TypeType)

    a = manager.eval_expr(src, "a")
    assert a
    assert a.temp == int_typetype.temp

    c = manager.eval_expr(src, "c")
    d = manager.eval_expr(src, "d")
    A = manager.eval_expr(src, "A")
    B = manager.eval_expr(src, "B")
    TA = manager.eval_expr(src, "TA")

    assert isinstance(c, TypeIns) and not isinstance(c, TypeType)
    assert isinstance(d, TypeIns) and not isinstance(d, TypeType)
    assert isinstance(A, TypeType)
    assert isinstance(B, TypeType)
    assert isinstance(TA, TypeType)

    assert TA.equiv(A)

    assert c.temp == A.temp
    assert d.temp == B.temp

    # test '__add__'
    astnode = parse_expr("c + d")
    eval_option = eval_expr(astnode, module_ins)
    # TODO: re-assert this
    # assert not eval_option.haserr()
    eval_res = eval_option.value
    assert isinstance(eval_res, TypeIns)
    assert eval_res.temp == B.temp

    # container
    e = manager.eval_expr(src, "e")
    assert isinstance(e, TypeIns) and not isinstance(e, TypeType)
    assert e.bindlist
    e_fst = e.bindlist[0]
    assert isinstance(e_fst, TypeIns) and not isinstance(e_fst, TypeType)
    assert e_fst.temp == int_typetype.temp

    f = manager.eval_expr(src, "f")
    assert isinstance(f, TypeIns) and not isinstance(f, TypeType)
    assert f.bindlist
    f_fst = f.bindlist[0]
    f_snd = f.bindlist[1]
    assert isinstance(f_fst, TypeIns) and not isinstance(f_fst, TypeType)
    assert isinstance(f_snd, TypeIns) and not isinstance(f_snd, TypeType)
    assert f_fst.temp == str_typetype.temp
    assert f_snd.temp == int_typetype.temp

    cmp_node = parse_expr("a < b")
    cmp_res_option = eval_expr(cmp_node, module_ins)
    assert not cmp_res_option.haserr()
    cmp_res = cmp_res_option.value
    assert cmp_res is bool_ins


def test_exprparse_mgf():
    error_assert("exprparse_mgf")
