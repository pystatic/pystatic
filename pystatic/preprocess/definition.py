import ast
from contextlib import contextmanager
from typing import Dict, Union, List, Tuple
from collections import OrderedDict
from pystatic.visitor import BaseVisitor
from pystatic.typesys import (TypeClassTemp, TypeType, TypeIns, any_ins,
                              TYPE_CHECKING)
from pystatic.message import MessageBox
from pystatic.symtable import Entry, SymTable, TableScope
from pystatic.preprocess.annotation import (parse_annotation,
                                            parse_comment_annotation,
                                            InvalidAnnSyntax)
from pystatic.preprocess.special_type import get_special_type_kind, try_special_type
from pystatic.preprocess.impt import split_import_stmt
from pystatic.uri import Uri, rel2absuri, uri_parent

if TYPE_CHECKING:
    from pystatic.manager import Manager


class TypeDefVisitor(BaseVisitor):
    def __init__(self, manager: 'Manager', symtable: 'SymTable',
                 mbox: 'MessageBox', uri: Uri) -> None:
        super().__init__()
        self.symtable = symtable
        self.mbox = mbox
        self.manager = manager
        self.uri = uri

        self._is_class = False
        self._clstemp = None

    @contextmanager
    def enter_class(self, clstemp):
        old_symtable = self.symtable
        old_is_class = self._is_class
        old_clstemp = self._clstemp

        new_symtable = self.symtable.new_symtable(TableScope.CLASS)
        self.symtable = new_symtable
        self._is_class = True
        self._clstemp = clstemp

        yield new_symtable

        self.symtable = old_symtable
        self._is_class = old_is_class
        self._clstemp = old_clstemp

    # def record_special_type(self, node: Union[ast.Assign, ast.AnnAssign]):
    #     kind = get_special_type_kind(node)
    #     if kind:
    #         pass

    # def visit_Assign(self, node: ast.Assign):
    #     self.record_special_type(node)

    # def visit_AnnAssign(self, node: ast.AnnAssign):
    #     self.record_special_type(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        clsname = node.name
        if self.symtable.lookup_local(clsname):
            # FIXME: class definition should take higher priority
            self.mbox.add_err(node, f'{clsname} is already defined')
        else:
            clstemp = TypeClassTemp(clsname, self.symtable, node)
            clstype = clstemp.get_default_type()
            entry = Entry(clstype, node)
            self.symtable.add_entry(clsname, entry)
            self.symtable.add_type_def(clsname, clstemp)

            # enter class scope
            with self.enter_class(clstemp):
                clstemp.set_inner_symtable(self.symtable)
                for body in node.body:
                    self.visit(body)

    def visit_Import(self, node: ast.Import):
        imp_dict = split_import_stmt(node, self.uri)
        self._add_import_info(node, imp_dict)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        imp_dict = split_import_stmt(node, self.uri)
        self._add_import_info(node, imp_dict)

    def _add_import_info(self, node: ast.AST,
                         imp_dict: Dict[Uri, List[Tuple[str, str]]]):
        for uri, tples in imp_dict.items():
            self.manager.add_target(uri)
            for asname, origin_name in tples:
                self.symtable.add_import_item(asname, uri, origin_name, node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        pass


# def deal_vardict(self, vardict: Dict[str, Entry]):
#     pass
#     # for key, val in vardict.items():
#     #     entry = self.symtable.lookup_local_entry(key)
#     #     if entry:
#     #         if get_entry_type_name(entry.get_real_type()) == 'typing.Any':
#     #             self.symtable.add_entry(key, val)
#     #         else:
#     #             assert val.defnode
#     #             self.mbox.add_err(val.defnode, f'{key} is already defined')
#     #     else:
#     #         self.symtable.add_entry(key, val)

# def _def_visitAssign(self, node: ast.Assign) -> Dict[str, Entry]:
#     """Get the variables defined in an ast.Assign node"""
#     # NOTE: current implementation is wrong
#     vardict: Dict[str, Entry] = OrderedDict()
#     if try_special_type(node, vardict, self.symtable, self.mbox):
#         return vardict
#     else:
#         comment = node.type_comment
#         if comment:
#             try:
#                 comment_type = parse_comment_annotation(
#                     comment, self.symtable)
#                 if isinstance(comment_type, TypeIns):
#                     assert isinstance(comment_type, TypeType)
#                     comment_ins = comment_type.getins()
#                 else:
#                     comment_ins = None
#                 for sub_node in reversed(node.targets):
#                     if isinstance(sub_node, ast.Name):
#                         vardict[sub_node.id] = Entry(sub_node, comment_ins)
#             except InvalidAnnSyntax:
#                 self.mbox.add_err(node, f'annotation syntax error')
#         return vardict

# def _def_visitAnnAssign(self, node: ast.AnnAssign) -> Dict[str, Entry]:
#     """Get the variables defined in an ast.AnnAssign node"""
#     # NOTE: current implementation may be wrong
#     vardict = OrderedDict()
#     if isinstance(node.target, ast.Name):
#         if try_special_type(node, vardict, self.symtable, self.mbox):
#             return vardict
#         else:
#             try:
#                 ann_type = parse_annotation(node.annotation, self.symtable)
#                 if ann_type:
#                     assert isinstance(ann_type, TypeType)
#                     ann_ins = ann_type.getins()
#                 else:
#                     ann_ins = None  # defer
#                 vardict[node.target.id] = Entry(node, ann_ins)
#             except InvalidAnnSyntax:
#                 self.mbox.add_err(node, f'annotation syntax error')
#     return vardict
