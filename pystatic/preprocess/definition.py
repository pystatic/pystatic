import ast
import logging
from contextlib import contextmanager
from typing import Dict, List, Tuple, Optional, TYPE_CHECKING
from pystatic.visitor import BaseVisitor
from pystatic.typesys import (TypeClassTemp, TpState)
from pystatic.message import MessageBox
from pystatic.symtable import Entry, SymTable, TableScope
from pystatic.preprocess.special_type import record_stp
from pystatic.preprocess.impt import split_import_stmt
from pystatic.uri import Uri

if TYPE_CHECKING:
    from pystatic.preprocess.main import Preprocessor

logger = logging.getLogger(__name__)


def get_definition(ast: 'ast.AST', worker: 'Preprocessor',
                   symtable: 'SymTable', mbox: 'MessageBox', uri: 'Uri'):
    return TypeDefVisitor(worker, symtable, mbox, uri).accept(ast)


def get_definition_in_method(ast: 'ast.AST', worker: 'Preprocessor',
                             symtable: 'SymTable', mbox: 'MessageBox',
                             uri: 'Uri', clstemp: 'TypeClassTemp'):
    pass


class TypeDefVisitor(BaseVisitor):
    def __init__(self, worker: 'Preprocessor', symtable: 'SymTable',
                 mbox: 'MessageBox', uri: Uri) -> None:
        super().__init__()
        self.symtable = symtable
        self.mbox = mbox
        self.worker = worker
        self.uri = uri

        self._is_class = False  # whether inside a method
        self._clstemp = None
        self._clsname: List[str] = []

    @contextmanager
    def enter_class(self, new_symtable, clstemp, clsname: str):
        old_symtable = self.symtable
        old_is_class = self._is_class
        old_clstemp = self._clstemp

        self.symtable = new_symtable
        self._is_class = True
        self._clstemp = clstemp
        self._clsname.append(clsname)

        yield new_symtable

        self.symtable = old_symtable
        self._is_class = old_is_class
        self._clstemp = old_clstemp
        self._clsname.pop()

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

    def visit_Assign(self, node: ast.Assign):
        # TODO: here we haven't add redefine warning and check consistence, the
        # def node is also incorrect
        name, entry = record_stp(node)
        if entry:
            assert name
            self.symtable.add_entry(name, entry)
            logger.debug(f'add type var {name}'
                         )  # because currently only support TypeVar
        else:
            for target in node.targets:
                name = self._is_new_def(target)
                if name:
                    self.symtable.add_entry(name, Entry(None, node))
                    logger.debug(f'add variable {name}')

    def visit_AnnAssign(self, node: ast.AnnAssign):
        name, entry = record_stp(node)
        if entry:
            assert name
            self.symtable.add_entry(name, entry)
            logger.debug(f'add type var {name}'
                         )  # because currently only support TypeVar
        else:
            name = self._is_new_def(node.target)
            if name:
                self.symtable.add_entry(name, Entry(None, node))
                logger.debug(f'add variable {name}')

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

            new_symtable = self.symtable.new_symtable(TableScope.CLASS)
            clstemp = TypeClassTemp(abs_clsname, TpState.FRESH, self.symtable,
                                    new_symtable, node)
            clstype = clstemp.get_default_type()
            entry = Entry(clstype, node)
            self.symtable.add_entry(clsname, entry)
            self.symtable.add_cls_def(clsname, clstemp)

            # enter class scope
            with self.enter_class(new_symtable, clstemp, clsname):
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
            self.worker.add_cache_target_uri(uri)
            for asname, origin_name in tples:
                self.symtable.add_import_item(asname, uri, origin_name, node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        logger.debug(f'add function {node.name}')
        self.symtable.add_fun_entry(node.name, Entry(None, node))


class MethodDefVisitor(TypeDefVisitor):
    def __init__(self, worker: 'Preprocessor', symtable: 'SymTable',
                 mbox: 'MessageBox', uri: 'Uri',
                 clstemp: 'TypeClassTemp') -> None:
        super().__init__(worker, symtable, mbox, uri)
        self._clstemp = clstemp
        self._is_class = True

    def visit_Assign(self, node: ast.Assign):
        pass

    def visit_AnnAssign(self, node: ast.AnnAssign):
        pass
