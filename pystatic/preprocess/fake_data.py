import ast
from typing import Optional, TYPE_CHECKING, Dict, List, TypeVar, Union
from pystatic.symid import (absolute_symidlist, SymId, symid2list,
                            rel2abssymid, symid_parent)
from pystatic.typesys import TypeAlias, TypeClassTemp, TypeIns, TypeType, any_ins
from pystatic.predefined import (TypeModuleTemp, TypePackageIns,
                                 TypePackageTemp, TypeVarIns)

from pystatic.symtable import SymTable, ImportNode, Entry
from pystatic.option import Option

if TYPE_CHECKING:
    from pystatic.manager import Manager

AssignNode = Union[ast.Assign, ast.AnnAssign]


class FakeData:
    def __init__(self, symtable: 'SymTable'):
        self.typevar_def: Dict[str, 'fake_typevar_def'] = {}
        self.fun: Dict[str, 'fake_fun_entry'] = {}
        self.local: Dict[str, 'fake_local_def'] = {}
        self.impt: Dict[str, 'fake_impt_entry'] = {}
        self.cls_def: Dict[str, 'fake_clsdef_entry'] = {}
        self.type_alias: Dict[str, 'fake_type_alias'] = {}

        self.symtable = symtable

    def name_collide(self, name: str):
        return (name in self.typevar_def or name in self.fun
                or name in self.local or name in self.cls_def)

    def add_cls_def(self, symtable: 'SymTable', temp: TypeClassTemp,
                    node: ast.ClassDef):
        name = node.name
        cls_def = fake_clsdef_entry(temp, node)
        self.cls_def[name] = cls_def
        symtable.add_type_def(name, temp)

    def add_typevar_def(self, name: str, typevar: 'TypeVarIns',
                        defnode: AssignNode):
        self.typevar_def[name] = fake_typevar_def(name, typevar, defnode)
        self.symtable.add_entry(name, Entry(typevar, defnode))

    def add_local_def(self, name: str, defnode: ast.AST):
        local_def = fake_local_def(name, defnode)
        self.local[name] = local_def

    def add_type_alias(self, alias: str, typetype: TypeType, defnode: ast.AST):
        type_alias = fake_type_alias(typetype, defnode)
        self.type_alias[alias] = type_alias
        self.symtable.add_entry(alias,
                                Entry(TypeAlias(alias, typetype), defnode))

    def getattribute(self, name: str, node: ast.AST) -> Option['TypeIns']:
        if name in self.cls_def:
            return Option(self.cls_def[name].clstemp.get_default_typetype())
        else:
            return Option(any_ins)


class fake_typevar_def:
    __slots__ = ['name', 'typevar', 'defnode']

    def __init__(self, name: str, typevar: 'TypeVarIns',
                 defnode: AssignNode) -> None:
        self.name = name
        self.typevar = typevar
        self.defnode = defnode


class fake_type_alias:
    __slots__ = ['typetype', 'defnode']

    def __init__(self, typetype: 'TypeType', defnode: ast.AST) -> None:
        self.typetype = typetype
        self.defnode = defnode


class fake_clsdef_entry:
    def __init__(self, clstemp: 'TypeClassTemp',
                 defnode: ast.ClassDef) -> None:
        assert isinstance(defnode, ast.ClassDef)
        self.defnode = defnode
        self.clstemp = clstemp

    @property
    def name(self):
        return self.defnode.name


class fake_fun_entry:
    def __init__(self, defnode: ast.FunctionDef) -> None:
        assert isinstance(defnode, ast.FunctionDef)
        self.defnodes = [defnode]

    def add_defnode(self, defnode: ast.FunctionDef):
        assert isinstance(defnode, ast.FunctionDef)
        assert defnode.name == self.defnodes[0].name
        self.defnodes.append(defnode)

    @property
    def name(self):
        return self.defnodes[0].name


class fake_local_def:
    __slots__ = ['name', 'defnode']

    def __init__(self, name: str, defnode: ast.AST) -> None:
        self.name = name
        self.defnode = defnode


class fake_impt_entry:
    __slots__ = ['symid', 'origin_name', 'asname', 'defnode']

    def __init__(self, symid: 'SymId', origin_name: str, asname: str,
                 defnode: ImportNode) -> None:
        self.symid = symid
        self.origin_name = origin_name
        self.asname = asname
        self.defnode = defnode

    def is_import_module(self):
        """Import the whole module?"""
        return self.origin_name == ''


def get_fake_data(symtable: 'SymTable') -> FakeData:
    if not hasattr(symtable, 'fake_data'):
        setattr(symtable, 'fake_data', FakeData(symtable))
    fake_data = getattr(symtable, 'fake_data')
    assert isinstance(fake_data, FakeData)
    return fake_data


def try_get_fake_data(symtable: 'SymTable') -> Optional[FakeData]:
    return getattr(symtable, 'fake_data', None)


def clear_fake_data(symtable: 'SymTable'):
    if hasattr(symtable, 'fake_data'):
        fake_data: FakeData = symtable.fake_data  # type: ignore
        for clsentry in fake_data.cls_def.values():
            tp_temp = clsentry.clstemp
            clear_fake_data(tp_temp.get_inner_symtable())
        del symtable.fake_data  # type: ignore


def add_fun_def(symtable: 'SymTable', fake_data: 'FakeData',
                node: ast.FunctionDef):
    name = node.name
    if name in fake_data.fun:
        fake_data.fun[name].defnodes.append(node)
    else:
        fake_data.fun[name] = fake_fun_entry(node)


def analyse_import_stmt(node: ImportNode,
                        symid: SymId) -> List[fake_impt_entry]:
    """Extract import information stored in import ast node."""
    info_list: List[fake_impt_entry] = []
    pkg_symid = symid_parent(symid)
    if isinstance(node, ast.Import):
        for alias in node.names:
            module_symid = alias.name
            as_name = alias.asname or module_symid
            info_list.append(fake_impt_entry(module_symid, '', as_name, node))

    elif isinstance(node, ast.ImportFrom):
        imp_name = '.' * node.level
        imp_name += node.module or ''
        module_symid = rel2abssymid(pkg_symid, imp_name)
        imported = []
        for alias in node.names:
            attr_name = alias.name
            as_name = alias.asname or attr_name
            imported.append((as_name, attr_name))
            info_list.append(
                fake_impt_entry(module_symid, attr_name, as_name, node))

    else:
        raise TypeError("node doesn't stand for an import statement")

    return info_list


def add_baseclass(temp: TypeClassTemp, basecls: 'TypeType'):
    if basecls not in temp.baseclass:
        temp.baseclass.append(basecls)


def get_cls_defnode(temp: TypeClassTemp):
    return temp._defnode


def update_symtable_import_cache(symtable: 'SymTable',
                                 entry: 'fake_impt_entry',
                                 manager: 'Manager') -> Optional[TypeIns]:
    symid = entry.symid

    symidlist = absolute_symidlist(symtable.glob_symid, symid)
    if not symidlist:
        return None

    cache = symtable.import_cache

    # get the initial module ins or package ins
    cur_symid = symidlist[0]
    cur_ins = cache.get_moduleins(cur_symid)

    if not cur_ins:
        temp = manager.get_module_temp(symidlist[0])
        if not temp:
            return None

        if isinstance(temp, TypePackageTemp):
            cur_ins = TypePackageIns(temp)
        else:
            assert isinstance(temp, TypeModuleTemp)
            cur_ins = temp.get_default_ins().value

        cache.set_moduleins(cur_symid, cur_ins)

    assert isinstance(cur_ins.temp, TypeModuleTemp)
    for i in range(1, len(symidlist)):
        if not isinstance(cur_ins, TypePackageIns):
            return None

        cur_symid += f'.{symidlist[i]}'
        if symidlist[i] not in cur_ins.submodule:
            temp = manager.get_module_temp(cur_symid)
            if not temp:
                return None

            assert isinstance(temp, TypeModuleTemp)
            if isinstance(temp, TypePackageTemp):
                cur_ins.add_submodule(symidlist[i], TypePackageIns(temp))
            else:
                if i != len(symidlist) - 1:
                    return None
                res_ins = temp.get_default_ins().value
                cur_ins.add_submodule(symidlist[i], res_ins)
                return res_ins

        cur_ins = cur_ins.submodule[symidlist[i]]

    assert cur_symid == entry.symid

    # If the source is a package then another module may be imported.
    # Example:
    # from fruit import apple
    # fruit is a package and apple is a module so pystatic need to add apple
    # to fruit's submodule list
    if isinstance(cur_ins, TypePackageIns):
        if not entry.is_import_module():
            cur_symid += f'.{entry.origin_name}'
            temp = manager.get_module_temp(cur_symid)

            if temp:
                cur_ins.add_submodule(entry.origin_name,
                                      temp.get_default_ins().value)

    return cur_ins
