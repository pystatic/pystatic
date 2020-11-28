import ast
from contextlib import contextmanager
from pystatic.visitor import BaseVisitor
from pystatic.message import MessageBox
from pystatic.reach import is_true, Reach
from pystatic.staticinfer import static_infer
from pystatic.target import BlockTarget, MethodTarget, FunctionTarget
from pystatic.preprocess.util import analyse_import_stmt
from pystatic.preprocess.prepinfo import *


def get_definition(target: 'BlockTarget', env: 'PrepEnvironment'):
    # TODO: seperate function block target and target
    cur_ast = target.ast
    cur_mbox = target.mbox
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
        target, PrepInfo(symtable, None, env, cur_mbox, is_special))

    TypeDefVisitor(env, prepinfo, cur_mbox).accept(cur_ast)


def get_definition_in_function(target: 'FunctionTarget',
                               env: 'PrepEnvironment'):
    cur_ast = target.ast
    cur_mbox = target.mbox
    assert isinstance(cur_ast, ast.FunctionDef)
    prepinfo = env.try_add_target_prepinfo(
        target, PrepInfo(target.symtable, None, env, cur_mbox, False))
    return TypeDefVisitor(env, prepinfo, cur_mbox, False).accept_func(cur_ast)


def get_definition_in_method(target: 'MethodTarget', env: 'PrepEnvironment'):
    cur_ast = target.ast
    cur_mbox = target.mbox
    assert isinstance(cur_ast, ast.FunctionDef)
    clstemp = target.clstemp
    prepinfo = env.try_add_target_prepinfo(
        target, PrepMethodInfo(clstemp, None, cur_mbox, env))
    assert isinstance(prepinfo, PrepMethodInfo)

    return TypeDefVisitor(env, prepinfo, cur_mbox, True).accept_func(cur_ast)


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

    def visit_If(self, node: ast.If):
        reach_res = static_infer(node.test, self.env.manager.config)
        if reach_res == Reach.UNKNOWN:
            for subnode in node.body:
                self.visit(subnode)
            for subnode in node.orelse:
                self.visit(subnode)
        else:
            setattr(node.test, 'reach', reach_res)
            if is_true(reach_res, False):
                for subnode in node.body:
                    self.visit(subnode)
            else:
                for subnode in node.orelse:
                    self.visit(subnode)
