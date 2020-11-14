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
    from pystatic.target import BlockTarget

AssignNode = Union[ast.Assign, ast.AnnAssign]


class PrepInfo:
    def __init__(self, symtable: 'SymTable'):
        self.typevar_def: Dict[str, 'prep_typevar_def'] = {}
        self.func: Dict[str, 'prep_func'] = {}
        self.local: Dict[str, 'prep_local_def'] = {}
        self.impt: Dict[str, 'prep_impt'] = {}
        self.cls_def: Dict[str, 'prep_clsdef'] = {}
        self.type_alias: Dict[str, 'prep_type_alias'] = {}

        self.symtable = symtable

    def name_collide(self, name: str):
        return (name in self.typevar_def or name in self.func
                or name in self.local or name in self.cls_def)

    def add_cls_def(self, temp: TypeClassTemp, prepinfo: 'PrepInfo',
                    def_prepinfo: 'PrepInfo', node: ast.ClassDef):
        name = node.name
        cls_def = prep_clsdef(temp, prepinfo, def_prepinfo, node)
        self.cls_def[name] = cls_def

    def add_typevar_def(self, name: str, typevar: 'TypeVarIns',
                        defnode: AssignNode):
        self.typevar_def[name] = prep_typevar_def(name, typevar, defnode)
        self.symtable.add_entry(name, Entry(typevar, defnode))

    def add_local_def(self, name: str, defnode: ast.AST):
        local_def = prep_local_def(name, defnode)
        self.local[name] = local_def

    def add_type_alias(self, alias: str, typetype: TypeType, defnode: ast.AST):
        type_alias = prep_type_alias(typetype, defnode)
        self.type_alias[alias] = type_alias
        self.symtable.add_entry(alias,
                                Entry(TypeAlias(alias, typetype), defnode))

    def add_func_def(self, node: ast.FunctionDef):
        name = node.name
        if name in self.func:
            self.func[name].defnodes.append(node)
        else:
            self.func[name] = prep_func(node)

    def get_prep_def(self, name: str):
        if name in self.cls_def:
            return self.cls_def[name]
        elif name in self.impt:
            return self.impt[name]

    def getattribute(self, name: str, node: ast.AST) -> Option['TypeIns']:
        if name in self.cls_def:
            return Option(self.cls_def[name].clstemp.get_default_typetype())
        else:
            return Option(any_ins)


class PrepEnvironment:
    def __init__(self, manager: 'Manager') -> None:
        self.manager = manager
        self.symid_prepinfo: Dict[str, 'PrepInfo'] = {}
        self.target_prepinfo: Dict['BlockTarget', 'PrepInfo'] = {}

    def get_prepinfo(self, symid: 'SymId'):
        if symid in self.symid_prepinfo:
            return self.symid_prepinfo[symid]
        else:
            return None

    def add_target_prepinfo(self, target: 'BlockTarget', prepinfo: 'PrepInfo'):
        self.target_prepinfo[target] = prepinfo

    def get_target_prepinfo(self, target: 'BlockTarget'):
        return self.target_prepinfo.get(target)


class prep_typevar_def:
    __slots__ = ['name', 'typevar', 'defnode']

    def __init__(self, name: str, typevar: 'TypeVarIns',
                 defnode: AssignNode) -> None:
        self.name = name
        self.typevar = typevar
        self.defnode = defnode


class prep_type_alias:
    __slots__ = ['typetype', 'defnode']

    def __init__(self, typetype: 'TypeType', defnode: ast.AST) -> None:
        self.typetype = typetype
        self.defnode = defnode


class prep_clsdef:
    def __init__(self, clstemp: 'TypeClassTemp', prepinfo: 'PrepInfo',
                 def_prepinfo: 'PrepInfo', defnode: ast.ClassDef) -> None:
        assert isinstance(defnode, ast.ClassDef)
        self.clstemp = clstemp
        self.prepinfo = prepinfo
        self.def_prepinfo = def_prepinfo
        self.defnode = defnode

    @property
    def name(self):
        return self.defnode.name


class prep_func:
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


class prep_local_def:
    __slots__ = ['name', 'defnode']

    def __init__(self, name: str, defnode: ast.AST) -> None:
        self.name = name
        self.defnode = defnode


class prep_impt:
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


def clear_prep_info(prep_info: 'PrepInfo'):
    for clsdef in prep_info.cls_def.values():
        clear_prep_info(clsdef.prepinfo)
    del prep_info
