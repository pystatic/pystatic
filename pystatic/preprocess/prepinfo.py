import ast
from typing import (Optional, TYPE_CHECKING, Dict, Union, List, Set, Final)
from pystatic.errorcode import *
from pystatic.target import Target
from pystatic.symid import SymId, symid2list
from pystatic.typesys import TypeAlias, TypeClassTemp, TypeIns, TypeType, any_ins
from pystatic.predefined import TypeVarIns, TypeFuncIns
from pystatic.symtable import ImportEntry, SymTable, ImportNode, Entry, TableScope
from pystatic.option import Option
from pystatic.message import MessageBox

if TYPE_CHECKING:
    from pystatic.manager import Manager
    from pystatic.target import BlockTarget

AssignNode = Union[ast.Assign, ast.AnnAssign]
PrepDef = Union['prep_cls', 'prep_func', 'prep_local']

LOCAL_NORMAL: Final[int] = 0
LOCAL_TYPEALIAS: Final[int] = 1
LOCAL_TYPEVAR: Final[int] = 2

PREP_NULL = 0
PREP_COMPLETE = 1

class PrepInfo:
    def __init__(self, symtable: 'SymTable', enclosing: Optional['PrepInfo'],
                 env: 'PrepEnvironment', mbox: 'MessageBox', is_special: bool):
        self.enclosing = enclosing
        self.is_special = is_special
        self.mbox = mbox

        self.cls: Dict[str, 'prep_cls'] = {}
        self.local: Dict[str, 'prep_local'] = {}
        self.func: Dict[str, 'prep_func'] = {}
        self.impt: Dict[str, 'prep_impt'] = {}

        self.typevar: Set[str] = set()
        self.type_alias: Set[str] = set()

        self.symtable = symtable
        self.env = env
        self.star_import: List[SymId] = []

    def name_collide(self, name: str):
        return (name in self.typevar or name in self.func
                or name in self.local or name in self.cls)
    
    @property
    def glob_symid(self) -> str:
        return self.symtable.glob_symid
    
    def new_cls_prepinfo(self, symtable: 'SymTable'):
        return PrepInfo(symtable, self, self.env, self.mbox, False)

    def add_cls_def(self, node: ast.ClassDef, mbox: 'MessageBox'):
        # TODO: check name collision
        clsname = node.name
        if (old_def := self.cls.get(clsname)):
            mbox.add_err(SymbolRedefine(node, clsname, old_def.defnode))
            return old_def.prepinfo

        if (old_def := self.local.get(clsname)):
            mbox.add_err(VarTypeCollide(node, clsname, old_def.defnode))
            self.local.pop(clsname)
        elif (old_def := self.func.get(clsname)):
            mbox.add_err(VarTypeCollide(node, clsname, old_def.defnode))
            self.func.pop(clsname)

        if (clstemp := self.symtable.get_type_def(clsname)):
            assert isinstance(clstemp, TypeClassTemp)
            new_symtable = clstemp.get_inner_symtable()

        else:
            new_symtable = self.symtable.new_symtable(clsname, TableScope.CLASS)
            clstemp = TypeClassTemp(clsname, self.symtable, new_symtable)

        new_prepinfo = self.new_cls_prepinfo(new_symtable)
        cls_def = prep_cls(clstemp, new_prepinfo, self, node)
        self.cls[clsname] = cls_def
        self.symtable.add_type_def(clsname, clstemp)
        self.symtable.add_entry(clsname, Entry(clstemp.get_default_typetype(), node))
        return new_prepinfo

    def add_func_def(self, node: ast.FunctionDef, mbox: 'MessageBox'):
        name = node.name
        if name in self.func:
            # name collision of different function is checked later
            self.func[name].defnodes.append(node)
        else:
            if (old_def := self.cls.get(name)):
                mbox.add_err(VarTypeCollide(old_def.defnode, name, node))
                return
            elif (old_def := self.local.get(name)):
                mbox.add_err(VarTypeCollide(node, name, old_def.defnode))
                self.local.pop(name)

            self.func[name] = prep_func(self, node)

    def add_local_def(self, node: AssignNode, is_method: bool, mbox: 'MessageBox'):
        def is_strong_def(node: AssignNode):
            """If a assignment has annotations or type_comments, then it's a strong
            definition.
            """
            return getattr(node, 'type_comment', None) or getattr(node, 'annotation', None)

        def is_self_def(node: AssignNode, target: ast.AST):
            """Whether test_node represents a form of "self.xxx = yyy"""
            if isinstance(target, ast.Attribute):
                if isinstance(target.value, ast.Name) and target.value.id == 'self':
                    attr = target.attr
                    assert isinstance(self, PrepMethodInfo)
                    if attr in self.var_attr:
                        # TODO: warning here because of redefinition
                        return
                    self.add_attr_def(attr, node)

        def deal_single_expr(target: ast.AST, defnode: AssignNode):
            if isinstance(target, ast.Name):
                name = target.id
                if self.is_special:
                    origin_local = self.symtable.lookup_local(name)
                    if origin_local:
                        return
                # NOTE: local_def finally added here
                if (old_def := self.cls.get(name)):
                    mbox.add_err(VarTypeCollide(old_def.defnode, name, defnode))
                    return
                elif (old_def := self.func.get(name)):
                    mbox.add_err(SymbolRedefine(defnode, name, old_def.defnode))
                    return
                elif (old_def := self.local.get(name)):
                    if is_strong_def(defnode):
                        old_astnode = old_def.defnode
                        if is_strong_def(old_astnode):
                            # variable defined earlier with type annotation
                            mbox.add_err(SymbolRedefine(defnode, name, old_astnode))
                            return
                    else:
                        return
                local_def = prep_local(name, self, defnode)
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

    def add_import_def(self, node: Union[ast.Import, ast.ImportFrom], infolist: List['prep_impt']):
        """Add import information to the symtable"""
        manager = self.env.manager
        for infoitem in infolist:
            # analyse all the package along the way
            symidlist = symid2list(infoitem.symid)
            cur_prefix = ''
            for subid in symidlist:
                if cur_prefix:
                    cur_prefix += f'.{subid}'
                else:
                    cur_prefix = subid
                manager.add_check_symid(cur_prefix, False)

            if infoitem.origin_name == '*':
                if infoitem.symid not in self.star_import:
                    self.star_import.append(infoitem.symid)

            if not infoitem.is_import_module():
                origin_symid = infoitem.symid + f'.{infoitem.origin_name}'
                if manager.is_module(origin_symid):
                    manager.add_check_symid(origin_symid, False)

            # TODO: error check name collision here
            self.impt[infoitem.asname] = infoitem

    def add_typevar_def(self, name: str, typevar: 'TypeVarIns',
                        defnode: AssignNode):
        assert name in self.local
        self.typevar.add(name)

    def add_type_alias(self, alias: str, typealias: TypeAlias,
                       defnode: AssignNode):
        assert alias in self.local
        self.type_alias.add(alias)
        self.symtable.add_entry(alias, Entry(typealias, defnode))

    def get_prep_def(self, name: str) -> Optional[PrepDef]:
        res = None
        if (res := self.cls.get(name)):
            return res
        elif (res := self.local.get(name)):
            return res
        elif (res := self.func.get(name)):
            return res
        elif (res := self.impt.get(name)):
            if res.value and not isinstance(res.value, TypeIns):
                return res.value
            else:
                return None

    def getattribute(self, name: str, node: ast.AST) -> Option['TypeIns']:
        res = None
        if (res := self.cls.get(name)):
            return Option(res.clstemp.get_default_typetype())
        elif (res := self.impt.get(name)):
            return Option(res.getins())
        elif (res := self.local.get(name)):
            return Option(res.getins())
        else:
            for star_impt in self.star_import:
                res = self.env.lookup(star_impt, name)
                if res:
                    if isinstance(res, TypeIns):
                        return Option(res)
                    else:
                        return Option(res.getins())

            res = self.symtable.legb_lookup(name)
            if res:
                return Option(res)
            elif self.enclosing:
                assert self.enclosing is not self
                return self.enclosing.getattribute(name, node)
            else:
                searched = {self.symtable.glob_symid}
                for module in self.star_import:
                    if module not in searched:
                        searched.add(module)
                        res = self.env.lookup(module, name)
                        if res:
                            return Option(res)
                return Option(any_ins)

    def dump(self):
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

        self.symtable.star_import.extend(self.star_import)


class PrepMethodInfo(PrepInfo):
    def __init__(self, clstemp: TypeClassTemp,
                 enclosing: Optional['PrepInfo'], mbox: 'MessageBox',
                 env: 'PrepEnvironment'):
        super().__init__(clstemp.get_inner_symtable(), enclosing, env, mbox, False)
        self.clstemp = clstemp
        self.var_attr: Dict[str, 'prep_local'] = {}

    def add_attr_def(self, name: str, defnode: AssignNode):
        attr_def = prep_local(name, self, defnode)
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
        if (prepinfo := self.symid_prepinfo.get(symid)):
            return prepinfo

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
        prepinfo = self.symid_prepinfo.get(module_symid)
        if prepinfo:
            res = prepinfo.get_prep_def(name)
            if res:
                return res
            else:
                for symid in prepinfo.star_import:
                    module_prepinfo = self.symid_prepinfo.get(symid)
                    if module_prepinfo:
                        res = module_prepinfo.get_prep_def(name)
                        if res:
                            return res

        module_ins = self.manager.get_module_ins(module_symid)
        if not module_ins:
            return None
        else:
            return module_ins._inner_symtable.legb_lookup(name)
    
    def clear(self):
        self.symid_prepinfo = {}
        for blk_target in self.target_prepinfo.keys():
            if isinstance(blk_target, Target):
                blk_target.module_ins.clear_consultant()
        self.target_prepinfo = {}


class prep_cls:
    def __init__(self, clstemp: 'TypeClassTemp', prepinfo: 'PrepInfo',
                 def_prepinfo: 'PrepInfo', defnode: ast.ClassDef) -> None:
        assert isinstance(defnode, ast.ClassDef)
        self.clstemp = clstemp
        self.prepinfo = prepinfo
        self.def_prepinfo = def_prepinfo
        self.defnode = defnode
        self.var_attr: Dict[str, prep_local] = {}
        self.stage = PREP_NULL

    @property
    def name(self):
        return self.defnode.name

    def add_attr(self, name: str, defnode: AssignNode):
        local_def = prep_local(name, self.prepinfo, defnode)
        self.var_attr[name] = local_def

    def getins(self) -> TypeType:
        return self.clstemp.get_default_typetype()


class prep_func:
    def __init__(self, def_prepinfo: PrepInfo, defnode: ast.FunctionDef) -> None:
        assert isinstance(defnode, ast.FunctionDef)
        self.defnodes = [defnode]
        self.def_prepinfo = def_prepinfo
        self.value: Optional[TypeFuncIns] = None
        self.stage = PREP_NULL
        self.name = defnode.name

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
    def __init__(self, name: str, def_prepinfo: 'PrepInfo', defnode: AssignNode) -> None:
        """
        :param typenode: if typenode is None then this symbol's stage is set to
        PREP_COMPLETE.
        """
        self.name = name
        self.defnode = defnode
        self.def_prepinfo = def_prepinfo
        self.value: Optional[TypeIns] = None

        self.type = LOCAL_NORMAL
        self.typenode = self.get_typenode(defnode)
        self.stage = PREP_NULL

    def get_typenode(self, node: AssignNode):
        if isinstance(node, ast.AnnAssign):
            return node.annotation
        else:
            assert isinstance(node, ast.Assign)
            if node.type_comment:
                try:
                    typenode = ast.parse(node.type_comment, mode='eval')
                    return typenode.body
                except SyntaxError:
                    return None
        return None

    def getins(self) -> TypeIns:
        return self.value or any_ins


class prep_impt:
    def __init__(self, symid: 'SymId', origin_name: str, asname: str,
                 def_prepinfo: 'PrepInfo', defnode: ImportNode) -> None:
        self.symid = symid
        self.origin_name = origin_name
        self.asname = asname
        self.defnode = defnode
        self.def_prepinfo = def_prepinfo
        self.value: Union[PrepDef, TypeIns, None] = None

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

