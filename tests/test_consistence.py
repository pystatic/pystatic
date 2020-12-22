import sys
from tests.util import get_manager_path

sys.path.append(".")
sys.path.append("..")

from pystatic.manager import Manager
from pystatic.consistent import is_consistent


def test_consistence():
    symid = "consistence"
    manager, _ = get_manager_path({"test_typeshed": True}, symid)
    manager.preprocess()
    list_int = manager.infer_expr(symid, "list_int")
    list_float = manager.infer_expr(symid, "list_float")
    list_str = manager.infer_expr(symid, "list_str")
    list_int2 = manager.infer_expr(symid, "list_int2")
    bool1 = manager.infer_expr(symid, "bool1")
    assert list_int
    assert list_str
    assert list_float
    assert list_int2
    assert bool1
    assert not is_consistent(list_int, list_str)
    assert is_consistent(list_int, list_int2)
