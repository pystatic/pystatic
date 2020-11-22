import ast
from pystatic.errorcode import *
from pystatic.target import Target
from typing import (Optional, Protocol, TYPE_CHECKING, Dict, Union)
from pystatic.symid import SymId
from pystatic.typesys import TypeAlias, TypeClassTemp, TypeIns, TypeType, any_ins
from pystatic.predefined import TypeVarIns, TypeFuncIns
from pystatic.symtable import ImportEntry, SymTable, ImportNode, Entry, TableScope
from pystatic.option import Option
from pystatic.message import MessageBox

if TYPE_CHECKING:
    from pystatic.manager import Manager
    from pystatic.target import BlockTarget

AssignNode = Union[ast.Assign, ast.AnnAssign]


class PrepInfoItem(Protocol):
    def getins(self) -> 'TypeIns':
        ...


class PrepInfo:
    def __init__(self, symtable: 'SymTable', enclosing: Optional['PrepInfo'],
                 is_special: bool):
        self.enclosing = enclosing
        self.is_special = is_special

        self.cls_def: Dict[str, 'prep_cls'] = {}
        self.typevar_def: Dict[str, 'prep_typevar'] = {}
        self.type_alias: Dict[str, 'prep_type_alias'] = {}
        self.local: Dict[str, 'prep_local'] = {}
        self.func: Dict[str, 'prep_func'] = {}
        self.impt: Dict[str, 'prep_impt'] = {}

        self.symtable = symtable

        self.tick = 1

    def name_collide(self, name: str):
        return (name in self.typevar_def or name in self.func
                or name in self.local or name in self.cls_def)

    def add_cls_def(self, node: ast.ClassDef, mbox: 'MessageBox'):
        # TODO: check name collision
        clsname = node.name
        if (old_cls_def := self.cls_def.get(clsname)):
            mbox.add_err(SymbolRedefine(node, clsname, old_cls_def.defnode))
            return

        if (old_local_def := self.local.get(clsname)):
            mbox.add_err(VarTypeCollide(node, clsname, old_local_def.defnode))
            self.local.pop(clsname)

        if (clstemp := self.symtable.get_type_def(clsname)):
            assert isinstance(clstemp, TypeClassTemp)
            new_symtable = clstemp.get_inner_symtable()

        else:
            new_symtable = self.symtable.new_symtable(clsname, TableScope.CLASS)
            clstemp = TypeClassTemp(clsname, self.symtable, new_symtable)
        
        new_prepinfo = PrepInfo(new_symtable, self, False)
        cls_def = prep_cls(clstemp, new_prepinfo, self, node)
        self.cls_def[clsname] = cls_def
        self.symtable.add_type_def(clsname, clstemp)
        self.symtable.add_entry(clsname, Entry(clstemp.get_default_typetype(), node))
        return new_prepinfo

    def add_typevar_def(self, name: str, typevar: 'TypeVarIns',
                        defnode: AssignNode):
        self.typevar_def[name] = prep_typevar(name, typevar, defnode)
        self.symtable.add_entry(name, Entry(typevar, defnode))

    def add_local_def(self, node: AssignNode, is_method: bool, mbox: 'MessageBox'):
        def is_self_def(node: AssignNode, target: ast.AST):
            """Whether test_node represents a form of "self.xxx = yyy"""
            if isinstance(target, ast.Attribute):
                if isinstance(target.value, ast.Name) and target.value.id == 'self':
                    attr = target.attr
                    assert isinstance(self, MethodPrepInfo)
                    if attr in self.var_attr:
                        # TODO: warning here because of redefinition
                        return
                    self.add_attr_def(attr, node)

        def deal_single_expr(target: ast.AST, defnode: AssignNode):
            if isinstance(target, ast.Name):
                name = target.id
                if not self.name_collide(name):
                    if self.is_special:
                        origin_local = self.symtable.lookup_local(name)
                        if origin_local:
                            return
                    # NOTE: local_def finally added here
                    local_def = prep_local(name, defnode)
                    self.local[name] = local_def
            elif isinstance(target, ast.Tuple):
                for elt in target.elts:
                    deal_single_expr(elt, defnode)
            elif is_method:
                is_self_def(defnode, target)

        if not node.value:
            assert isinstance(node, ast.AnnAssign)
            deal_single_expr(node.target, node)
        else:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    deal_single_expr(target, node)

            elif isinstance(node, ast.AnnAssign):
                deal_single_expr(node.target, node)

            else:
                raise TypeError()

    def add_type_alias(self, alias: str, typealias: TypeAlias,
                       defnode: AssignNode):
        prep = prep_type_alias(typealias, defnode)
        self.type_alias[alias] = prep
        self.symtable.add_entry(alias, Entry(typealias, defnode))

    def add_func_def(self, node: ast.FunctionDef):
        name = node.name
        if name in self.func:
            self.func[name].defnodes.append(node)
        else:
            self.func[name] = prep_func(node)

    def get_prep_def(self, name: str) -> Optional[PrepInfoItem]:
        if name in self.cls_def:
            return self.cls_def[name]
        elif name in self.local:
            return self.local[name]
        elif name in self.func:
            return self.func[name]
        elif name in self.impt:
            return self.impt[name]

    def getattribute(self, name: str, node: ast.AST) -> Option['TypeIns']:
        if name in self.cls_def:
            return Option(self.cls_def[name].clstemp.get_default_typetype())
        elif name in self.impt:
            impt = self.impt[name]
            return Option(impt.getins())
        else:
            res = self.symtable.lookup(name)
            if res:
                return Option(res)
            elif self.enclosing:
                assert self.enclosing is not self
                return self.enclosing.getattribute(name, node)
            else:
                return Option(any_ins)

    def dump(self):
        for name, clsdef in self.cls_def.items():
            # classes must have been added before
            # TODO: remove this
            assert not self.symtable.getattribute(name,
                                                  clsdef.defnode).haserr()

        for name, typevar_def in self.typevar_def.items():
            value = typevar_def.getins()
            self.symtable.add_entry(name, Entry(value, typevar_def.defnode))
        for name, local in self.local.items():
            value = local.getins()
            self.symtable.add_entry(name, Entry(value, local.defnode))
        for name, func in self.func.items():
            value = func.getins()
            self.symtable.add_entry(name, Entry(value, func.defnode))

        for name, impt in self.impt.items():
            value = impt.getins()
            self.symtable.import_cache.add_cache(impt.symid, impt.origin_name,
                                                 value)
            self.symtable.add_entry(
                name, ImportEntry(impt.symid, impt.origin_name, impt.defnode))


class MethodPrepInfo(PrepInfo):
    def __init__(self, clstemp: TypeClassTemp,
                 enclosing: Optional['PrepInfo']):
        super().__init__(clstemp.get_inner_symtable(), enclosing, False)
        self.clstemp = clstemp
        self.var_attr: Dict[str, 'prep_local'] = {}

    def add_attr_def(self, name: str, defnode: AssignNode):
        attr_def = prep_local(name, defnode)
        self.var_attr[name] = attr_def

    def dump(self):
        super().dump()
        for name, var_attr in self.var_attr.items():
            self.clstemp.var_attr[name] = var_attr.getins()


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
        assert target not in self.target_prepinfo
        self.target_prepinfo[target] = prepinfo
        if isinstance(target, Target):
            self.symid_prepinfo[target.symid] = prepinfo

    def try_add_target_prepinfo(self, target: 'BlockTarget',
                                prepinfo: 'PrepInfo'):
        """Try to add a prepinfo into environment

        If target already in environment, then prepinfo won't be added.

        Return the prepinfo in the environment
        """
        if target not in self.target_prepinfo:
            self.target_prepinfo[target] = prepinfo
            if isinstance(target, Target):
                self.symid_prepinfo[target.symid] = prepinfo
            return prepinfo
        return self.target_prepinfo[target]

    def get_target_prepinfo(self, target: 'BlockTarget'):
        return self.target_prepinfo.get(target)

    def lookup(self, module_symid: 'SymId', name: str):
        preinfo = self.symid_prepinfo.get(module_symid)
        if preinfo:
            res = preinfo.get_prep_def(name)
            if res:
                return res

        module_temp = self.manager.get_module_temp(module_symid)
        if not module_temp:
            return None
        else:
            return module_temp.get_inner_symtable().lookup(name)


class prep_typevar:
    __slots__ = ['name', 'typevar', 'defnode']

    def __init__(self, name: str, typevar: 'TypeVarIns',
                 defnode: AssignNode) -> None:
        self.name = name
        self.typevar = typevar
        self.defnode = defnode

    def getins(self) -> TypeVarIns:
        return self.typevar


class prep_type_alias:
    __slots__ = ['defnode', 'value']

    def __init__(self, typealias: 'TypeAlias', defnode: AssignNode) -> None:
        self.value = typealias
        self.defnode = defnode

    def getins(self) -> TypeAlias:
        return self.value


class prep_cls:
    def __init__(self, clstemp: 'TypeClassTemp', prepinfo: 'PrepInfo',
                 def_prepinfo: 'PrepInfo', defnode: ast.ClassDef) -> None:
        assert isinstance(defnode, ast.ClassDef)
        self.clstemp = clstemp
        self.prepinfo = prepinfo
        self.def_prepinfo = def_prepinfo
        self.defnode = defnode
        self.var_attr: Dict[str, prep_local] = {}

    @property
    def name(self):
        return self.defnode.name

    def add_attr(self, name: str, defnode: AssignNode):
        local_def = prep_local(name, defnode)
        self.var_attr[name] = local_def

    def getins(self) -> TypeType:
        return self.clstemp.get_default_typetype()


class prep_func:
    def __init__(self, defnode: ast.FunctionDef) -> None:
        assert isinstance(defnode, ast.FunctionDef)
        self.defnodes = [defnode]
        self.value: Optional[TypeFuncIns] = None

    def add_defnode(self, defnode: ast.FunctionDef):
        assert isinstance(defnode, ast.FunctionDef)
        assert defnode.name == self.defnodes[0].name
        self.defnodes.append(defnode)

    @property
    def defnode(self) -> ast.AST:
        return self.defnodes[0]

    def getins(self) -> TypeIns:
        return self.value or any_ins


class prep_local:
    __slots__ = ['name', 'defnode', 'value']

    def __init__(self, name: str, defnode: AssignNode) -> None:
        assert isinstance(defnode, ast.Assign) or isinstance(
            defnode, ast.AnnAssign)
        self.name = name
        self.defnode = defnode
        self.value: Optional[TypeIns] = None

    def getins(self) -> TypeIns:
        return self.value or any_ins


class prep_impt:
    __slots__ = [
        'symid', 'origin_name', 'asname', 'defnode', 'def_prepinfo', 'value'
    ]

    def __init__(self, symid: 'SymId', origin_name: str, asname: str,
                 def_prepinfo: 'PrepInfo', defnode: ImportNode) -> None:
        self.symid = symid
        self.origin_name = origin_name
        self.asname = asname
        self.defnode = defnode
        self.def_prepinfo = def_prepinfo
        self.value: Union[PrepInfoItem, TypeIns, None] = None

    def is_import_module(self):
        """Import the whole module?"""
        return self.origin_name == ''

    def getins(self) -> TypeIns:
        if not self.value:
            return any_ins
        if isinstance(self.value, TypeIns):
            return self.value
        else:
            return self.value.getins()


def clear_prep_info(prep_info: 'PrepInfo'):
    for clsdef in prep_info.cls_def.values():
        clear_prep_info(clsdef.prepinfo)
    del prep_info
