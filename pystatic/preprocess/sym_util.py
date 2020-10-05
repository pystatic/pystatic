import ast
import logging
from pystatic.uri import absolute_urilist, Uri, uri2list
from typing import Optional, TYPE_CHECKING, Any
from pystatic.typesys import (TypeClassTemp, TypeIns, TypeModuleTemp,
                              TypePackageIns, TypeTemp, TypePackageTemp)
from pystatic.symtable import SymTable, ImportNode

if TYPE_CHECKING:
    from pystatic.preprocess.main import Preprocessor

logger = logging.getLogger(__name__)


class fake_fun_entry:
    def __init__(self, name: str, defnode: ast.FunctionDef) -> None:
        self.name = name
        self.defnodes = [defnode]

    def add_defnode(self, defnode: ast.FunctionDef):
        self.defnodes.append(defnode)


class fake_local_entry:
    def __init__(self, name: str, defnode: ast.AST) -> None:
        self.name = name
        self.defnode = defnode


class fake_imp_entry:
    def __init__(self, uri: 'Uri', origin_name: str,
                 defnode: ImportNode) -> None:
        self.uri = uri
        self.origin_name = origin_name
        self.defnode = defnode


def add_cls_def(symtable: SymTable, name: str, temp: TypeClassTemp):
    symtable._cls_defs[name] = temp


def add_spt_def(symtable: SymTable, name: str, temp: TypeTemp):
    symtable._spt_types[name] = temp


def add_import_item(symtable: 'SymTable', name: str, uri: 'Uri',
                    origin_name: str, defnode: 'ImportNode'):
    """Add import information to the symtable, this will add fake_imp_entry to
    the local scope.
    """
    symtable._import_nodes.append(defnode)

    # add fake import entry to the local scope
    # TODO: warning if name collision happens
    if isinstance(defnode, ast.ImportFrom):
        tmp_entry = fake_imp_entry(uri, origin_name, defnode)
        symtable.local[name] = tmp_entry  # type: ignore


def add_fun_def(symtable: 'SymTable', name: str, node: ast.FunctionDef):
    """Add function definition information to the symtable, this will add
    fake_fun_entry to the _func_defs of the symtable."""
    if name in symtable._func_defs:
        assert isinstance(symtable._func_defs[name], fake_fun_entry)
        symtable._func_defs[name].add_defnode(node)  # type: ignore
    else:
        symtable._func_defs[name] = fake_fun_entry(name, node)  # type: ignore


def add_local_var(symtable: 'SymTable', name: str, node: ast.AST):
    # add fake local variable entry to the local scope
    symtable.local[name] = fake_local_entry(name, node)  # type: ignore


def add_uri_symtable(symtable: 'SymTable', uri: str,
                     worker: 'Preprocessor') -> Optional[TypeIns]:
    """Update symtable's import tree with uri"""
    urilist = absolute_urilist(symtable.glob_uri, uri)
    assert urilist

    # get the initial module ins or package ins
    cur_uri = urilist[0]
    cur_ins: TypeIns
    if urilist[0] in symtable._import_tree:
        cur_ins = symtable._import_tree[urilist[0]]
    else:
        temp = worker.get_module_temp(urilist[0])
        if not temp:
            return None

        if isinstance(temp, TypePackageTemp):
            cur_ins = TypePackageIns(temp)
        else:
            assert isinstance(temp, TypeModuleTemp)
            cur_ins = temp.get_default_ins()

        symtable._import_tree[urilist[0]] = cur_ins

    assert isinstance(cur_ins.temp, TypeModuleTemp)

    for i in range(1, len(urilist)):
        if not isinstance(cur_ins, TypePackageIns):
            return None

        cur_uri += f'.{urilist[i]}'
        if urilist[i] not in cur_ins.submodule:
            temp = worker.get_module_temp(cur_uri)
            if not temp:
                return None

            assert isinstance(temp, TypeModuleTemp)
            if isinstance(temp, TypePackageTemp):
                cur_ins.add_submodule(urilist[i], TypePackageIns(temp))
            else:
                if i != len(urilist) - 1:
                    return None
                res_ins = temp.get_default_ins()
                cur_ins.add_submodule(urilist[i], res_ins)
                return res_ins

        cur_ins = cur_ins.submodule[urilist[i]]

    return cur_ins


def search_uri_symtable(symtable: 'SymTable', uri: str) -> Optional[TypeIns]:
    urilist = uri2list(uri)
    assert urilist
    cur_ins = symtable._import_tree[urilist[0]]
    for i in range(1, len(urilist)):
        cur_ins = cur_ins.getattribute(urilist[i])
        if not cur_ins:
            return None
    return cur_ins
