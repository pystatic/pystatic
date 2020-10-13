import ast
import logging
from contextlib import contextmanager
from typing import Dict, List, Tuple, Optional, TYPE_CHECKING, Union
from pystatic.visitor import BaseVisitor
from pystatic.typesys import (TypeClassTemp, TpState, TypeVarIns, TypeVarTemp,
                              TypeType)
from pystatic.message import MessageBox
from pystatic.symtable import Entry, SymTable, TableScope, ImportNode
from pystatic.uri import Uri
from pystatic.exprparse import eval_expr
from pystatic.preprocess.sym_util import (add_import_item, add_fun_def,
                                          add_local_var, add_cls_def,
                                          analyse_import_stmt, ImportInfoItem)

if TYPE_CHECKING:
    from pystatic.preprocess.main import Preprocessor
    from pystatic.target import BlockTarget, MethodTarget

logger = logging.getLogger(__name__)


def get_definition(target: 'BlockTarget', worker: 'Preprocessor',
                   mbox: 'MessageBox'):
    cur_ast = target.ast
    symtable = target.symtable
    uri = target.uri
    assert cur_ast
    return TypeDefVisitor(worker, symtable, mbox, uri).accept(cur_ast)


def get_definition_in_method(target: 'MethodTarget', worker: 'Preprocessor',
                             mbox: 'MessageBox'):
    cur_ast = target.ast
    symtable = target.symtable
    clstemp = target.clstemp
    uri = target.uri
    assert isinstance(cur_ast, ast.FunctionDef)
    return TypeDefVisitor(worker, symtable, mbox, uri, clstemp,
                          True).accept_func(cur_ast)


class TypeDefVisitor(BaseVisitor):
    def __init__(self,
                 worker: 'Preprocessor',
                 symtable: 'SymTable',
                 mbox: 'MessageBox',
                 uri: Uri,
                 clstemp: 'TypeClassTemp' = None,
                 is_method=False) -> None:
        super().__init__()
        self.symtable = symtable
        self.mbox = mbox
        self.worker = worker
        self.uri = uri

        self.clstemp: Optional['TypeClassTemp'] = clstemp
        self._is_method = is_method

        self._clsname: List[str] = []

        self.glob_uri = symtable.glob.uri  # the module's uri

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
            tmp_attr = {
                'node': node,
                'symtable': self.symtable,
            }
            assert self.clstemp
            self.clstemp._add_defer_var(attr, tmp_attr)

    def accept_func(self, node: ast.FunctionDef):
        for stmt in node.body:
            self.visit(stmt)

    @contextmanager
    def enter_class(self, new_symtable, clsname: str):
        old_symtable = self.symtable
        old_is_method = self._is_method

        self.symtable = new_symtable
        self._clsname.append(clsname)
        self._is_method = False

        yield new_symtable

        self._is_method = old_is_method
        self._clsname.pop()
        self.symtable = old_symtable

    @property
    def cur_clsname(self):
        return '.'.join(self._clsname)

    def _is_new_def(self, node: ast.AST) -> Optional[str]:
        """Whether the node stands for a new definition"""
        if isinstance(node, ast.Name):
            if self.symtable.lookup_local_entry(node.id) is None:
                return node.id
            else:
                return None
        return None

    def _is_typevar(self, node: ast.expr) -> Optional[TypeVarIns]:
        if isinstance(node, ast.Call):
            f_ins = eval_expr(node, self.symtable, self.mbox, False)
            if isinstance(f_ins, TypeType) and isinstance(
                    f_ins.temp, TypeVarTemp):
                res = eval_expr(node, self.symtable, self.mbox, False)
                assert isinstance(res, TypeVarIns)
                return res
        return None

    def visit_Assign(self, node: ast.Assign):
        # TODO: here pystatic haven't add redefine warning and check consistence
        tpvarins = self._is_typevar(node.value)
        if tpvarins:
            assert isinstance(tpvarins, TypeVarIns)
            last_target = node.targets[-1]
            assert isinstance(last_target, ast.Name), "TODO: add error here"

            tpvarins.tpvar_name = last_target.id
            self.symtable.add_entry(last_target.id, Entry(tpvarins, node))
        else:
            for target in node.targets:
                name = self._is_new_def(target)
                if name:
                    add_local_var(self.symtable, name, node)
                    logger.debug(f'add variable {name}')
                elif self._is_method:
                    self._try_attr(node, target)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        assert False, "not implemented yet"
        name, entry = record_stp(self.glob_uri, node)
        if entry:
            assert name
            self.symtable.add_entry(name, entry)
            logger.debug(f'add type var {name}'
                         )  # because currently only support TypeVar
        else:
            name = self._is_new_def(node.target)
            if name:
                add_local_var(self.symtable, name, node)
                logger.debug(f'add variable {name}')
            elif self._is_method:
                self._try_attr(node, node.target)

    def visit_ClassDef(self, node: ast.ClassDef):
        clsname = node.name
        if self.symtable.lookup_local(clsname):
            # FIXME: class definition should take higher priority
            self.mbox.add_err(node, f'{clsname} is already defined')
        else:
            cur_clsname = self.cur_clsname
            if cur_clsname:
                abs_clsname = cur_clsname + '.' + clsname
            else:
                abs_clsname = clsname

            new_symtable = self.symtable.new_symtable(clsname,
                                                      TableScope.CLASS)
            clstemp = TypeClassTemp(abs_clsname, self.glob_uri, TpState.FRESH,
                                    self.symtable, new_symtable, node)
            clstype = clstemp.get_default_typetype()
            entry = Entry(clstype, node)
            self.symtable.add_entry(clsname, entry)
            add_cls_def(self.symtable, clsname, clstemp)

            # enter class scope
            with self.enter_class(new_symtable, clsname):
                for body in node.body:
                    self.visit(body)

    def visit_Import(self, node: ast.Import):
        info_list = analyse_import_stmt(node, self.uri)
        self._add_import_info(node, info_list)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        info_list = analyse_import_stmt(node, self.uri)
        self._add_import_info(node, info_list)

    def _add_import_info(self, node: 'ImportNode',
                         info_list: List[ImportInfoItem]):
        """Add import information to the symtable.

        imp_dict:
            import information dict returned by split_import_stmt.
        """
        read_typing = False  # flag, if True typing module has been read
        typing_temp = None
        for infoitem in info_list:
            # when the imported module is typing.py, pystatic will add symbols
            # imported from it as soon as possible because some types (such as
            # TypeVar) may affect how pystatic judge whether an assignment
            # statement is a special type definition or not.
            if infoitem.uri == 'typing':
                if not read_typing:
                    typing_temp = self.worker.get_module_temp('typing')

                if typing_temp:
                    if infoitem.is_import_module:
                        self.symtable.add_entry(
                            'typing', Entry(typing_temp.get_default_ins(),
                                            node))
                    else:
                        symtb = typing_temp.get_inner_symtable()
                        entry = symtb.lookup_local_entry(infoitem.origin_name)

                        if isinstance(entry, Entry):
                            tpins = entry.get_type()
                            self.symtable.add_entry(infoitem.asname,
                                                    Entry(tpins, node))
                            return
            self.worker.add_cache_target_uri(infoitem.uri)
            add_import_item(self.symtable, infoitem, node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        add_fun_def(self.symtable, node.name, node)
