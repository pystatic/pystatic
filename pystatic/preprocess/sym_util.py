import ast
import logging
from typing import Optional, TYPE_CHECKING, Union, Dict, Tuple, List
from pystatic.uri import absolute_urilist, Uri, uri2list, rel2absuri
from pystatic.typesys import (TypeClassTemp, TypeIns, TypeModuleTemp,
                              TypePackageIns, TypeTemp, TypePackageTemp,
                              TypeType, TpState, any_ins)
from pystatic.symtable import SymTable, ImportNode

if TYPE_CHECKING:
    from pystatic.preprocess.main import Preprocessor


class FakeData:
    def __init__(self):
        self.fun: Dict[str, 'fake_fun_entry'] = {}
        self.local: Dict[str, 'fake_local_entry'] = {}
        self.impt: Dict[str, 'fake_impt_entry'] = {}


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


class fake_impt_entry:
    __slots__ = ['uri', 'origin_name', 'asname', 'defnode']

    def __init__(self, uri: 'Uri', origin_name: str, asname: str,
                 defnode: ImportNode) -> None:
        self.uri = uri
        self.origin_name = origin_name
        self.asname = asname
        self.defnode = defnode

    def is_import_module(self):
        """Import the whole module?"""
        return self.origin_name == ''


def get_fake_data(symtable: 'SymTable') -> FakeData:
    if not hasattr(symtable, 'fake_data'):
        setattr(symtable, 'fake_data', FakeData())
    fake_data = getattr(symtable, 'fake_data')
    assert isinstance(fake_data, FakeData)
    return fake_data


def try_get_fake_data(symtable: 'SymTable') -> Optional[FakeData]:
    return getattr(symtable, 'fake_data', None)


def add_cls_def(symtable: SymTable, name: str, temp: TypeClassTemp):
    symtable._cls_defs[name] = temp


def add_spt_def(symtable: SymTable, name: str, temp: TypeTemp):
    symtable._spt_types[name] = temp


def add_fun_def(symtable: 'SymTable', name: str, node: ast.FunctionDef):
    fake_data = get_fake_data(symtable)
    if name in fake_data.fun:
        fake_data.fun[name].defnodes.append(node)
    else:
        fake_data.fun[name] = fake_fun_entry(name, node)


def add_local_var(symtable: 'SymTable', name: str, node: ast.AST):
    fake_data = get_fake_data(symtable)
    entry = fake_local_entry(name, node)
    fake_data.local[name] = entry


def analyse_import_stmt(node: ImportNode, uri: Uri) -> List[fake_impt_entry]:
    """Extract import information stored in import ast node."""
    info_list: List[fake_impt_entry] = []
    if isinstance(node, ast.Import):
        for alias in node.names:
            module_uri = alias.name
            as_name = alias.asname or module_uri
            info_list.append(fake_impt_entry(module_uri, '', as_name, node))

    elif isinstance(node, ast.ImportFrom):
        imp_name = '.' * node.level
        imp_name += node.module or ''
        module_uri = rel2absuri(uri, imp_name)
        imported = []
        for alias in node.names:
            attr_name = alias.name
            as_name = alias.asname or attr_name
            imported.append((as_name, attr_name))
            info_list.append(
                fake_impt_entry(module_uri, attr_name, as_name, node))

    else:
        raise TypeError("node doesn't stand for an import statement")

    return info_list


def add_baseclass(temp: TypeClassTemp, basecls: 'TypeType'):
    if basecls not in temp.baseclass:
        temp.baseclass.append(basecls)


def get_cls_defnode(temp: TypeClassTemp):
    return temp._defnode


def set_temp_state(temp: TypeTemp, st: TpState):
    temp._resolve_state = st


def get_temp_state(temp: TypeTemp) -> TpState:
    return temp._resolve_state


def update_symtable_import_cache(symtable: 'SymTable',
                                 entry: 'fake_impt_entry',
                                 worker: 'Preprocessor') -> Optional[TypeIns]:
    """Update symtable's import cache"""
    uri = entry.uri

    urilist = absolute_urilist(symtable.glob_uri, uri)
    if not urilist:
        return None

    cache = symtable.import_cache

    # get the initial module ins or package ins
    cur_uri = urilist[0]
    cur_ins = cache.get_moduleins(cur_uri)

    if not cur_ins:
        temp = worker.get_module_temp(urilist[0])
        if not temp:
            return None

        if isinstance(temp, TypePackageTemp):
            cur_ins = TypePackageIns(temp)
        else:
            assert isinstance(temp, TypeModuleTemp)
            cur_ins = temp.get_default_ins()

        cache.set_moduleins(cur_uri, cur_ins)

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

    assert cur_uri == entry.uri

    # If the source is a package then another module may be imported.
    # Example:
    # from fruit import apple
    # fruit is a package and apple is a module so pystatic need to add apple
    # to fruit's submodule list
    if isinstance(cur_ins, TypePackageIns):
        if not entry.is_import_module():
            cur_uri += f'.{entry.origin_name}'
            temp = worker.get_module_temp(cur_uri)

            if temp:
                cur_ins.add_submodule(entry.origin_name,
                                      temp.get_default_ins())

    return cur_ins
