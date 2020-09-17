import ast
from typing import Dict
from collections import OrderedDict
from pystatic.visitor import BaseVisitor
from pystatic.typesys import (Deferred, TypeClassTemp, TypeType, TypeIns,
                              any_ins, get_entry_type_name)
from pystatic.env import Environment
from pystatic.message import MessageBox
from pystatic.symtable import Entry, SymTable, Tabletype
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
                if get_entry_type_name(entry.get_real_type()) == 'typing.Any':
                    symtable.add_entry(key, val)
                else:
                    assert val.defnode
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
        clsname = node.name
        if self.env.symtable.lookup_local(clsname):
            self.mbox.add_err(node, f'{clsname} is already defined')
        else:
            clstemp = TypeClassTemp(clsname)
            clstype = clstemp.get_default_type()
            self.env.symtable.add_entry(clsname, Entry(clstype, node))

            # base classes
            for base_node in node.bases:
                entry_tp = parse_annotation(base_node, self.env, self.mbox)
                if entry_tp:
                    entry = Entry(entry_tp)
                    entry_name = get_entry_type_name(entry_tp)
                    self.env.symtable.add_anon_entry(entry)
                    assert isinstance(entry_tp, TypeType) and not isinstance(
                        entry_tp, Deferred)
                    clstemp.add_base(entry_name, entry)

            # enter class scope
            cls_symtable = self.env.new_symtable(Tabletype.CLASS)
            cls_symtable.set_attach(clstemp)
            self.env.symtable.add_subtable(cls_symtable)
            with self.env.enter_class(cls_symtable):
                for body in node.body:
                    self.visit(body)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        pass


def _def_visitAssign(env: Environment, node: ast.Assign,
                     mbox: 'MessageBox') -> Dict[str, Entry]:
    """Get the variables defined in an ast.Assign node"""
    # NOTE: current implementation is wrong
    vardict: Dict[str, Entry] = OrderedDict()
    if try_special_type(node, vardict, env, mbox):
        return vardict
    else:
        comment = node.type_comment
        if comment:
            comment_type = parse_comment_annotation(comment, env, mbox)
            if isinstance(comment_type, TypeIns):
                assert isinstance(comment_type, TypeType)
                comment_ins = comment_type.getins()
            elif comment_type:
                # Deferred
                assert isinstance(comment_type, Deferred)
                comment_ins = comment_type
            else:
                comment_ins = any_ins
            for sub_node in reversed(node.targets):
                if isinstance(sub_node, ast.Name):
                    vardict[sub_node.id] = Entry(comment_ins, sub_node)
        return vardict


def _def_visitAnnAssign(env: Environment, node: ast.AnnAssign,
                        mbox: 'MessageBox') -> Dict[str, Entry]:
    """Get the variables defined in an ast.AnnAssign node"""
    # NOTE: current implementation may be wrong
    vardict = OrderedDict()
    if try_special_type(node, vardict, env, mbox):
        return vardict
    else:
        ann_type = parse_annotation(node.annotation, env, mbox)
        if isinstance(ann_type, TypeIns):
            assert isinstance(ann_type, TypeType)
            ann_ins = ann_type.getins()
        elif ann_type:
            # Deferred
            assert isinstance(ann_type, Deferred)
            ann_ins = ann_type
        else:
            ann_ins = any_ins
        if isinstance(node.target, ast.Name):
            # this assignment is also a definition
            vardict[node.target.id] = Entry(ann_ins, node)
    return vardict
