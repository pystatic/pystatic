import ast
from typing import Dict, Tuple
from collections import OrderedDict
from pystatic.visitor import BaseVisitor
from pystatic.typesys import any_ins, TypeIns
from pystatic.env import Environment
from pystatic.message import MessageBox
from pystatic.preprocess.annotation import (parse_comment_annotation,
                                            parse_annotation)
from pystatic.preprocess.special_type import try_special_type


class DefVisitor(BaseVisitor):
    def __init__(self, env: 'Environment', mbox: 'MessageBox') -> None:
        super().__init__()
        self.env = env
        self.mbox = mbox

    def deal_vardict(self, vardict: Dict[str, Tuple[ast.AST, TypeIns]]):
        symtable = self.env.symtable
        for key, val in vardict.items():
            entry = symtable.get_local_entry(key)
            if entry:
                if entry.tnode.get_realtype().name == 'typing.Any':
                    symtable.add_entry(key, val[0], val[1])
                else:
                    self.mbox.add_err(val[0], f'{key} is already defined')
            else:
                symtable.add_entry(key, val[0], val[1])

    def visit_AnnAssign(self, node: ast.AnnAssign):
        vardict = _def_visitAnnAssign(self.env, node, self.mbox)
        self.deal_vardict(vardict)

    def visit_Assign(self, node: ast.Assign):
        vardict = _def_visitAssign(self.env, node, self.mbox)
        self.deal_vardict(vardict)

    def visit_ClassDef(self, node: ast.ClassDef):
        pass

    def visit_FunctionDef(self, node: ast.FunctionDef):
        pass


def _def_visitAssign(env: Environment, node: ast.Assign,
                     mbox: 'MessageBox') -> Dict[str, Tuple[ast.AST, TypeIns]]:
    """Get the variables defined in an ast.Assign node"""
    vardict = OrderedDict()
    if try_special_type(node, vardict, env, mbox):
        return vardict
    else:
        comment_type = parse_comment_annotation(node, env)
        comment_type = comment_type if comment_type else any_ins
        for sub_node in reversed(node.targets):
            if isinstance(sub_node, ast.Name):
                vardict[sub_node.id] = (sub_node, comment_type)
        return vardict


def _def_visitAnnAssign(
        env: Environment, node: ast.AnnAssign,
        mbox: 'MessageBox') -> Dict[str, Tuple[ast.AST, TypeIns]]:
    """Get the variables defined in an ast.AnnAssign node"""
    vardict = OrderedDict()
    if try_special_type(node, vardict, env, mbox):
        return vardict
    else:
        ann_ins = parse_annotation(node.annotation, env, False)
        ann_ins = ann_ins if ann_ins else any_ins
        if isinstance(node.target, ast.Name):
            # this assignment is also a definition
            vardict[node.target.id] = ann_ins
    return vardict
