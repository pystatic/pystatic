import ast
from contextlib import contextmanager
from typing import List, Optional, TYPE_CHECKING, Union
from pystatic.visitor import BaseVisitor, NoGenVisitor
from pystatic.typesys import TypeClassTemp, TypeType
from pystatic.predefined import TypeVarTemp, TypeVarIns
from pystatic.message import MessageBox
from pystatic.symtable import Entry, SymTable, TableScope, ImportNode
from pystatic.symid import SymId
from pystatic.exprparse import eval_expr
from pystatic.target import BlockTarget, MethodTarget

from pystatic.preprocess.util import omit_inst_typetype
from pystatic.preprocess.fake_data import *

if TYPE_CHECKING:
    from pystatic.manager import Manager


def get_definition(target: 'BlockTarget', manager: 'Manager',
                   mbox: 'MessageBox'):
    cur_ast = target.ast
    symtable = target.symtable
    symid = target.symid
    assert cur_ast

    TypeDefVisitor(manager, symtable, mbox, symid).accept(cur_ast)
    fake_data = get_fake_data(symtable)
    for name, clsentry in fake_data.cls_def.items():
        clstype = clsentry.clstemp.get_default_typetype()
        # predefined typetype may be re-added to symtable here
        entry = Entry(clstype, clsentry.defnode)
        symtable.add_entry(name, entry)


def get_definition_in_method(target: 'MethodTarget', manager: 'Manager',
                             mbox: 'MessageBox'):
    cur_ast = target.ast
    symtable = target.symtable
    clstemp = target.clstemp
    symid = target.symid
    assert isinstance(cur_ast, ast.FunctionDef)
    return TypeDefVisitor(manager, symtable, mbox, symid, clstemp,
                          True).accept_func(cur_ast)


class TypeDefVisitor(BaseVisitor):
    def __init__(self,
                 manager: 'Manager',
                 symtable: 'SymTable',
                 mbox: 'MessageBox',
                 symid: SymId,
                 clstemp: 'TypeClassTemp' = None,
                 is_method=False) -> None:
        super().__init__()
        self.symtable = symtable
        self.fake_data = get_fake_data(symtable)
        self.mbox = mbox
        self.manager = manager
        self.symid = symid

        self.clstemp: Optional['TypeClassTemp'] = clstemp
        self._is_method = is_method

        self._clsname: List[str] = []

        self.glob_symid = symtable.glob.symid  # the module's symid

    def _is_self_def(self, node: ast.AST) -> Optional[str]:
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name):
                if node.value.id == 'self':
                    return node.attr
        return None

    def _try_attr(self, node: ast.AST, target: ast.AST):
        attr = self._is_self_def(target)
        if attr:
            # Unfortunately this is a hack to put temporary information
            # on class template's var_attr
            assert self.clstemp
            inner_sym = self.clstemp.get_inner_symtable()
            fake_data = try_get_fake_data(inner_sym)
            if fake_data and attr in fake_data.local:
                return
            if attr in inner_sym.local:
                return

            if attr in self.clstemp.var_attr:
                return

            tmp_attr = {
                'node': node,
                'symtable': self.symtable,
            }
            self.clstemp.var_attr[attr] = tmp_attr  # type: ignore

    def accept_func(self, node: ast.FunctionDef):
        for stmt in node.body:
            self.visit(stmt)

    @contextmanager
    def enter_class(self, new_symtable: 'SymTable', clsname: str):
        old_symtable = self.symtable
        old_is_method = self._is_method
        old_fake_data = self.fake_data

        self.symtable = new_symtable
        self.fake_data = get_fake_data(new_symtable)
        self._clsname.append(clsname)
        self._is_method = False

        yield new_symtable

        self._is_method = old_is_method
        self._clsname.pop()
        self.symtable = old_symtable
        self.fake_data = old_fake_data

    @property
    def cur_clsname(self):
        return '.'.join(self._clsname)

    def collect_typevar(self, node: AssignNode) -> Optional[TypeVarIns]:
        def get_name(node: ast.AST) -> Optional[str]:
            if isinstance(node, ast.Name):
                return node.id
            return None

        value_node = node.value
        if isinstance(value_node, ast.Call):
            f_ins = eval_expr(value_node.func, self.symtable).value
            if isinstance(f_ins, TypeType) and isinstance(f_ins.temp, TypeVarTemp):
                typevar = eval_expr(node, self.symtable).value
                assert isinstance(typevar, TypeVarIns)

                if isinstance(node, ast.AnnAssign):
                    typevar_name = get_name(node)
                    assert typevar_name  # TODO: error
                elif isinstance(node, ast.Assign):
                    assert node.targets[0]  # TODO: error
                    typevar_name = get_name(node.targets[0])
                    assert typevar_name  # TODO: error
                else:
                    raise TypeError()

                self.fake_data.add_typevar_def(typevar_name, typevar, node)
                return typevar
        return None
    
    def collect_type_alias(self, node: AssignNode) -> Optional[TypeType]:
        if isinstance(node, ast.AnnAssign):
            # assignment with type annotation is not a type alias.
            return None

        if node.value:
            typetype = omit_inst_typetype(node.value, self.fake_data, False)
            if typetype:
                if isinstance(typetype, tuple):
                    raise NotImplementedError()
                else:
                    if len(node.targets) != 1:
                        return None
                    else:
                        target = node.targets[0]
                
                    if isinstance(target, ast.Name):
                        self.fake_data.add_type_alias(target.id, typetype, node)
                        return typetype
                    else:
                        raise NotImplementedError()
        return None

    def collect_definition(self, node: Union[ast.Assign, ast.AnnAssign]):
        def check_single_expr(target: ast.AST, defnode: ast.AST):
            if isinstance(target, ast.Name):
                name = target.id
                if not self.fake_data.name_collide(name):
                    self.fake_data.add_local_def(name, defnode)
            elif isinstance(target, ast.Tuple):
                for elt in target.elts:
                    check_single_expr(elt, defnode)
            elif self._is_method:
                self._try_attr(defnode, target)

        if not node.value:
            assert isinstance(node, ast.AnnAssign)
            check_single_expr(node.target, node)
        else:
            if not self.collect_type_alias(node):
                if not self.collect_typevar(node):
                    if isinstance(node, ast.Assign):
                        for target in node.targets:
                            check_single_expr(target, node)

                    elif isinstance(node, ast.AnnAssign):
                        check_single_expr(node.target, node)

                    else:
                        raise TypeError()

    def visit_Assign(self, node: ast.Assign):
        # TODO: here pystatic haven't add redefine warning and check consistence
        self.collect_definition(node)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        self.collect_definition(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        clsname = node.name

        if (clstemp := self.symtable.get_type_def(clsname)):
            assert isinstance(clstemp, TypeClassTemp)
            new_symtable = clstemp.get_inner_symtable()
            # predefined class may not set its defnode
            clstemp._defnode = node

        else:
            cur_clsname = self.cur_clsname
            if cur_clsname:
                abs_clsname = cur_clsname + '.' + clsname
            else:
                abs_clsname = clsname

            new_symtable = self.symtable.new_symtable(clsname,
                                                      TableScope.CLASS)
            clstemp = TypeClassTemp(abs_clsname, self.symtable, new_symtable, node)

        assert isinstance(clstemp, TypeClassTemp)
        self.fake_data.add_cls_def(self.symtable, clstemp, node)

        # enter class scope
        with self.enter_class(new_symtable, clsname):
            for body in node.body:
                self.visit(body)

    def visit_Import(self, node: ast.Import):
        info_list = analyse_import_stmt(node, self.symid)
        self._add_import_info(node, info_list)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        info_list = analyse_import_stmt(node, self.symid)
        self._add_import_info(node, info_list)

    def _add_import_info(self, node: 'ImportNode',
                         info_list: List[fake_impt_entry]):
        """Add import information to the symtable.

        info_list:
            import information dict returned by split_import_stmt.
        """
        fake_data = get_fake_data(self.symtable)
        self.symtable.import_cache.add_import_node(node)

        read_typing = False  # flag, if True typing module has been read
        typing_temp = None
        for infoitem in info_list:
            # when the imported module is typing.py, pystatic will add symbols
            # imported from it as soon as possible because some types (such as
            # TypeVar) may affect how pystatic judge whether an assignment
            # statement stands for a special type definition or not.
            if infoitem.symid == 'typing':
                if not read_typing:
                    typing_temp = self.manager.get_module_temp('typing')
                    read_typing = True

                if typing_temp:
                    if infoitem.is_import_module():
                        self.symtable.add_entry(
                            'typing',
                            Entry(typing_temp.get_default_ins().value, node))
                    else:
                        symtb = typing_temp.get_inner_symtable()
                        typing_tpins = symtb.lookup_local(infoitem.origin_name)

                        if typing_tpins:
                            self.symtable.add_entry(infoitem.asname,
                                                    Entry(typing_tpins, node))
                            continue

            # must analyse all possible module that will be used when
            # constructing symtable's import_cache because when constructing
            # the import_cache it rely on the manager to return the correct
            # module.

            # analyse all the package along the way
            symidlist = symid2list(infoitem.symid)
            cur_prefix = ''
            for subid in symidlist:
                if cur_prefix:
                    cur_prefix += f'.{subid}'
                else:
                    cur_prefix = subid
                self.manager.add_check_symid(cur_prefix)

            if not infoitem.is_import_module():
                origin_symid = infoitem.symid + f'.{infoitem.origin_name}'
                if self.manager.is_module(origin_symid):
                    self.manager.add_check_symid(origin_symid)

            fake_data.impt[infoitem.asname] = infoitem

    def visit_FunctionDef(self, node: ast.FunctionDef):
        add_fun_def(self.symtable, self.fake_data, node)
