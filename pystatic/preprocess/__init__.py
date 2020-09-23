from typing import TYPE_CHECKING
from pystatic.preprocess.definition import TypeDefVisitor
from pystatic.preprocess.predefined import get_builtin_env, get_init_env
from pystatic.preprocess.cls import resolve_cls_def
from pystatic.preprocess.impt import resolve_import_type
from pystatic.preprocess.typeins import resolve_typeins

if TYPE_CHECKING:
    import ast
    from pystatic.env import Environment
    from pystatic.message import MessageBox
    from pystatic.manager import Manager, Target
    from pystatic.symtable import SymTable
    from pystatic.uri import Uri


def get_definition(ast: 'ast.AST', manager: 'Manager', symtable: 'SymTable',
                   mbox: 'MessageBox', uri: 'Uri'):
    return TypeDefVisitor(manager, symtable, mbox, uri).accept(ast)
