import ast
from contextlib import contextmanager
from typing import List, Optional, Union
from pystatic.visitor import BaseVisitor
from pystatic.typesys import TypeClassTemp
from pystatic.message import MessageBox
from pystatic.symtable import TableScope, ImportNode
from pystatic.target import BlockTarget, MethodTarget
from pystatic.preprocess.util import analyse_import_stmt
from pystatic.preprocess.prepinfo import *


def get_definition(target: 'BlockTarget', env: 'PrepEnvironment',
                   mbox: 'MessageBox'):
    # TODO: seperate function block target and target
    cur_ast = target.ast
    symtable = target.symtable
    symid = target.symid

    assert cur_ast
    assert not env.get_prepinfo(symid), "call get_definition with the same symid is invalid"

    prepinfo = env.try_add_target_prepinfo(target, PrepInfo(symtable, None))

    TypeDefVisitor(env, prepinfo, mbox).accept(cur_ast)


def get_definition_in_method(target: 'MethodTarget', env: 'PrepEnvironment',
                             mbox: 'MessageBox'):
    cur_ast = target.ast
    assert isinstance(cur_ast, ast.FunctionDef)
    clstemp = target.clstemp
    prepinfo = env.try_add_target_prepinfo(target, MethodPrepInfo(clstemp, None))
    assert isinstance(prepinfo, MethodPrepInfo)

    return TypeDefVisitor(env, prepinfo, mbox, True).accept_func(cur_ast)


class TypeDefVisitor(BaseVisitor):
    def __init__(self,
                 env: 'PrepEnvironment',
                 prepinfo: 'PrepInfo',
                 mbox: 'MessageBox',
                 is_method=False) -> None:
        super().__init__()
        self.prepinfo = prepinfo
        self.mbox = mbox
        self.env = env
        self.glob_symid = prepinfo.symtable.glob.symid  # the module's symid
        self.is_method = is_method

    def _is_self_def(self, node: ast.AST) -> Optional[str]:
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name):
                if node.value.id == 'self':
                    return node.attr
        return None

    def _try_attr(self, node: AssignNode, target: ast.AST):
        attr = self._is_self_def(target)
        if attr:
            prepinfo = self.prepinfo
            assert isinstance(prepinfo, MethodPrepInfo)
            if attr in prepinfo.var_attr:
                # TODO: warning here because of redefinition
                return
            prepinfo.add_attr_def(attr, node)

    def accept_func(self, node: ast.FunctionDef):
        for stmt in node.body:
            self.visit(stmt)

    @contextmanager
    def enter_class(self, new_prepinfo: 'PrepInfo'):
        old_prepinfo = self.prepinfo
        old_is_method = self.is_method

        self.prepinfo = new_prepinfo
        self.is_method = False
        assert not isinstance(new_prepinfo, MethodPrepInfo)
        yield new_prepinfo

        self.is_method = old_is_method
        self.prepinfo = old_prepinfo

    def collect_definition(self, node: Union[ast.Assign, ast.AnnAssign]):
        def check_single_expr(target: ast.AST, defnode: AssignNode):
            if isinstance(target, ast.Name):
                name = target.id
                if not self.prepinfo.name_collide(name):
                    self.prepinfo.add_local_def(name, defnode)
            elif isinstance(target, ast.Tuple):
                for elt in target.elts:
                    check_single_expr(elt, defnode)
            elif self.is_method:
                self._try_attr(defnode, target)

        if not node.value:
            assert isinstance(node, ast.AnnAssign)
            check_single_expr(node.target, node)
        else:
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

        # TODO: error: redefinition
        if self.prepinfo.name_collide(clsname):
            raise NotImplementedError("name collision with class not handled yet")

        if (clstemp := self.prepinfo.symtable.get_type_def(clsname)):
            assert isinstance(clstemp, TypeClassTemp)
            new_symtable = clstemp.get_inner_symtable()

        else:
            new_symtable = self.prepinfo.symtable.new_symtable(clsname, TableScope.CLASS)
            clstemp = TypeClassTemp(clsname, self.prepinfo.symtable, new_symtable)

        assert isinstance(clstemp, TypeClassTemp)

        new_prepinfo = PrepInfo(new_symtable, self.prepinfo)
        self.prepinfo.add_cls_def(clstemp, new_prepinfo, self.prepinfo, node)
        self.prepinfo.symtable.add_entry(clsname, Entry(clstemp.get_default_typetype(), node))

        # enter class scope
        with self.enter_class(new_prepinfo):
            for body in node.body:
                self.visit(body)

    def visit_Import(self, node: ast.Import):
        info_list = analyse_import_stmt(self.prepinfo, node, self.glob_symid)
        self._add_import_info(node, info_list)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        info_list = analyse_import_stmt(self.prepinfo, node, self.glob_symid)
        self._add_import_info(node, info_list)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.prepinfo.add_func_def(node)

    def _add_import_info(self, node: 'ImportNode',
                         info_list: List[prep_impt]):
        """Add import information to the symtable"""
        manager = self.env.manager
        for infoitem in info_list:
            # analyse all the package along the way
            symidlist = symid2list(infoitem.symid)
            cur_prefix = ''
            for subid in symidlist:
                if cur_prefix:
                    cur_prefix += f'.{subid}'
                else:
                    cur_prefix = subid
                manager.add_check_symid(cur_prefix, False)

            if not infoitem.is_import_module():
                origin_symid = infoitem.symid + f'.{infoitem.origin_name}'
                if manager.is_module(origin_symid):
                    manager.add_check_symid(origin_symid, False)

            # TODO: error check name collision here
            self.prepinfo.impt[infoitem.asname] = infoitem
