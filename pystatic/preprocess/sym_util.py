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

logger = logging.getLogger(__name__)


class FakeData:
    def __init__(self):
        self.fun: Dict[str, 'fake_fun_entry'] = {}
        self.local: Dict[str, 'fake_local_entry'] = {}
        self.impt: List['fake_impt_entry'] = []


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
    def __init__(self, uri: 'Uri', origin_name: str,
                 defnode: ImportNode) -> None:
        self.uri = uri
        self.origin_name = origin_name
        self.defnode = defnode


def get_fake_data(symtable: 'SymTable') -> FakeData:
    if not hasattr(symtable, 'fake_data'):
        setattr(symtable, 'fake_data', FakeData())
    fake_data = getattr(symtable, 'fake_data')
    assert isinstance(fake_data, FakeData)
    return fake_data


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


class ImportInfoItem:
    __slots__ = ['uri', 'origin_name', 'asname']

    def __init__(self, uri: str, origin_name: str, asname: str) -> None:
        self.uri = uri
        self.origin_name = origin_name
        self.asname = asname

    @property
    def is_import_module(self):
        """Import the whole module?"""
        return self.origin_name == ''


def analyse_import_stmt(node: Union[ast.Import, ast.ImportFrom],
                        uri: Uri) -> List[ImportInfoItem]:
    """Extract import information stored in import ast node.

    Return an dict that maps uri to a list of ImportInfoItem.
    """
    info_list: List[ImportInfoItem] = []
    if isinstance(node, ast.Import):
        for alias in node.names:
            module_uri = alias.name
            as_name = alias.asname or module_uri
            info_list.append(ImportInfoItem(module_uri, '', as_name))

    elif isinstance(node, ast.ImportFrom):
        imp_name = '.' * node.level
        imp_name += node.module or ''
        module_uri = rel2absuri(uri, imp_name)
        imported = []
        for alias in node.names:
            attr_name = alias.name
            as_name = alias.asname or attr_name
            imported.append((as_name, attr_name))
            info_list.append(ImportInfoItem(module_uri, attr_name, as_name))

    else:
        raise TypeError("node doesn't stand for an import statement")

    return info_list


def add_import(symtable: 'SymTable', infoitem: 'ImportInfoItem',
               defnode: 'ImportNode'):
    """Store import information.

    def node will be simply appended to symtable's _import_nodes list.

    If defnode represents a ImportFrom node, then an fake_imp_entry will be
    added to the symtable's fake_data.
    """
    symtable._import_nodes.append(defnode)

    # TODO: warning if name collision happens
    if isinstance(defnode, ast.ImportFrom):
        tmp_entry = fake_impt_entry(infoitem.uri, infoitem.origin_name,
                                    defnode)
        fake_data = get_fake_data(symtable)
        fake_data.impt.append(tmp_entry)


def add_baseclass(temp: TypeClassTemp, basecls: 'TypeType'):
    if basecls not in temp.baseclass:
        temp.baseclass.append(basecls)


def get_cls_defnode(temp: TypeClassTemp):
    return temp._defnode


def set_temp_state(temp: TypeTemp, st: TpState):
    temp._resolve_state = st


def get_temp_state(temp: TypeTemp) -> TpState:
    return temp._resolve_state


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
        # TODO: warning here
        cur_ins = cur_ins.getattribute(urilist[i], None).value
        if not cur_ins:
            return None
    return cur_ins
