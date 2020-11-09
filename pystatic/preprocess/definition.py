import ast
from contextlib import contextmanager
from typing import List, Optional, TYPE_CHECKING
from pystatic.visitor import BaseVisitor
from pystatic.typesys import TypeClassTemp, TypeType
from pystatic.predefined import TypeVarTemp, TypeVarIns
from pystatic.message import MessageBox
from pystatic.symtable import Entry, SymTable, TableScope, ImportNode
from pystatic.symid import SymId
from pystatic.exprparse import eval_expr
from pystatic.preprocess.sym_util import *
from pystatic.target import BlockTarget, MethodTarget

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
    for name, clsentry in fake_data.cls_defs.items():
        clstype = clsentry.clstemp.get_default_typetype()
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

    def _is_new_def(self, node: ast.AST) -> Optional[str]:
        """Whether the node stands for a new definition"""
        if isinstance(node, ast.Name):
            fake_data = get_fake_data(self.symtable)
            name = node.id
            if (name in fake_data.fun or name in fake_data.local
                    or name in fake_data.impt):
                return None
            else:
                return name
        return None

    def _is_typevar(self, node: ast.expr) -> Optional[TypeVarIns]:
        if isinstance(node, ast.Call):
            f_ins = eval_expr(node.func, self.symtable).value
            if isinstance(f_ins, TypeType) and isinstance(
                    f_ins.temp, TypeVarTemp):
                res = eval_expr(node, self.symtable).value
                assert isinstance(res, TypeVarIns), "TODO"
                return res
        return None

    def visit_Assign(self, node: ast.Assign):
        # TODO: here pystatic haven't add redefine warning and check consistence
        tpvarins = self._is_typevar(node.value)
        if tpvarins:
            assert isinstance(tpvarins, TypeVarIns)
            last_target = node.targets[-1]
            assert isinstance(last_target, ast.Name), "TODO"

            tpvarins.tpvar_name = last_target.id
            self.symtable.add_entry(last_target.id, Entry(tpvarins, node))

        else:
            for target in node.targets:
                name = self._is_new_def(target)
                if name:
                    add_local_var(self.symtable, self.fake_data, name, node)
                elif self._is_method:
                    self._try_attr(node, target)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        tpvarins = None
        if node.value:
            tpvarins = self._is_typevar(node.value)
        if tpvarins:
            assert isinstance(tpvarins, TypeVarIns)
            last_target = node.target
            assert isinstance(last_target, ast.Name), "TODO"

            tpvarins.tpvar_name = last_target.id
            self.symtable.add_entry(last_target.id, Entry(tpvarins, node))

        else:
            name = self._is_new_def(node.target)
            if name:
                add_local_var(self.symtable, self.fake_data, name, node)
            elif self._is_method:
                self._try_attr(node, node.target)

    def visit_ClassDef(self, node: ast.ClassDef):
        clsname = node.name

        if (clstemp := self.symtable.get_type_def(clsname)):
            assert isinstance(clstemp, TypeClassTemp)
            new_symtable = clstemp.get_inner_symtable()

        else:
            cur_clsname = self.cur_clsname
            if cur_clsname:
                abs_clsname = cur_clsname + '.' + clsname
            else:
                abs_clsname = clsname

            new_symtable = self.symtable.new_symtable(clsname,
                                                      TableScope.CLASS)
            clstemp = TypeClassTemp(abs_clsname, self.symtable, new_symtable, node)

        # clstype = clstemp.get_default_typetype()
        # entry = Entry(clstype, node)
        # self.symtable.add_entry(clsname, entry)
        assert isinstance(clstemp, TypeClassTemp)
        add_cls_def(self.symtable, self.fake_data, clstemp, node)

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
