import ast
from contextlib import contextmanager
from typing import List, Optional, Union
from pystatic.visitor import BaseVisitor
from pystatic.typesys import TypeClassTemp
from pystatic.message import MessageBox
from pystatic.symid import symid2list
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

    if isinstance(target, Target):
        is_special = target.is_special
    else:
        is_special = False

    assert cur_ast
    assert not env.get_prepinfo(
        symid), "call get_definition with the same symid is invalid"

    prepinfo = env.try_add_target_prepinfo(
        target, PrepInfo(symtable, None, env, is_special))

    TypeDefVisitor(env, prepinfo, mbox).accept(cur_ast)


def get_definition_in_method(target: 'MethodTarget', env: 'PrepEnvironment',
                             mbox: 'MessageBox'):
    cur_ast = target.ast
    assert isinstance(cur_ast, ast.FunctionDef)
    clstemp = target.clstemp
    prepinfo = env.try_add_target_prepinfo(target,
                                           PrepMethodInfo(clstemp, None, env))
    assert isinstance(prepinfo, PrepMethodInfo)

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

    def accept_func(self, node: ast.FunctionDef):
        for stmt in node.body:
            self.visit(stmt)

    @contextmanager
    def enter_class(self, new_prepinfo: 'PrepInfo'):
        old_prepinfo = self.prepinfo
        old_is_method = self.is_method

        self.prepinfo = new_prepinfo
        self.is_method = False
        assert not isinstance(new_prepinfo, PrepMethodInfo)
        yield new_prepinfo

        self.is_method = old_is_method
        self.prepinfo = old_prepinfo

    def visit_Assign(self, node: ast.Assign):
        # TODO: here pystatic haven't add redefine warning and check consistence
        self.prepinfo.add_local_def(node, self.is_method, self.mbox)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        self.prepinfo.add_local_def(node, self.is_method, self.mbox)

    def visit_ClassDef(self, node: ast.ClassDef):
        new_prepinfo = self.prepinfo.add_cls_def(node, self.mbox)
        # enter class scope
        with self.enter_class(new_prepinfo):
            for body in node.body:
                self.visit(body)

    def visit_Import(self, node: ast.Import):
        infolist = analyse_import_stmt(self.prepinfo, node, self.glob_symid)
        self.prepinfo.add_import_def(node, infolist)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        infolist = analyse_import_stmt(self.prepinfo, node, self.glob_symid)
        self.prepinfo.add_import_def(node, infolist)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.prepinfo.add_func_def(node, self.mbox)
