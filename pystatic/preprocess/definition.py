import ast
from typing import Dict
from collections import OrderedDict
from pystatic.visitor import BaseVisitor
from pystatic.typesys import any_ins
from pystatic.env import Environment
from pystatic.message import MessageBox
from pystatic.symtable import Entry
from pystatic.preprocess.annotation import (parse_annotation,
                                            parse_comment_annotation)
from pystatic.preprocess.special_type import try_special_type


class DefVisitor(BaseVisitor):
    def __init__(self, env: 'Environment', mbox: 'MessageBox') -> None:
        super().__init__()
        self.env = env
        self.mbox = mbox

    def deal_vardict(self, vardict: Dict[str, Entry]):
        symtable = self.env.symtable
        for key, val in vardict.items():
            entry = symtable.lookup_local_entry(key)
            if entry:
                if entry.get_real_type().name == 'typing.Any':
                    symtable.add_entry(key, val)
                else:
                    self.mbox.add_err(val.defnode, f'{key} is already defined')
            else:
                symtable.add_entry(key, val)

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
                     mbox: 'MessageBox') -> Dict[str, Entry]:
    """Get the variables defined in an ast.Assign node"""
    vardict = OrderedDict()
    if try_special_type(node, vardict, env, mbox):
        return vardict
    else:
        comment = node.type_comment
        if comment:
            comment_type = parse_comment_annotation(comment, env, mbox)
            comment_type = comment_type if comment_type else any_ins
            for sub_node in reversed(node.targets):
                if isinstance(sub_node, ast.Name):
                    vardict[sub_node.id] = (sub_node, comment_type)
        return vardict


def _def_visitAnnAssign(env: Environment, node: ast.AnnAssign,
                        mbox: 'MessageBox') -> Dict[str, Entry]:
    """Get the variables defined in an ast.AnnAssign node"""
    vardict = OrderedDict()
    if try_special_type(node, vardict, env, mbox):
        return vardict
    else:
        ann_ins = parse_annotation(node.annotation, env, mbox)
        ann_ins = ann_ins if ann_ins else any_ins
        if isinstance(node.target, ast.Name):
            # this assignment is also a definition
            vardict[node.target.id] = Entry(node, ann_ins)
    return vardict
