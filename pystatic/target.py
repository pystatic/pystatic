import enum
import ast
from typing import TYPE_CHECKING, Optional
from pystatic.typesys import TypeModuleTemp, TpState

if TYPE_CHECKING:
    from pystatic.uri import Uri
    from pystatic.symtable import SymTable


class Stage(enum.IntEnum):
    """Number ascends as the analysis going deeper"""
    PreParse = 0
    PreSymtable = 1


class Target:
    def __init__(self,
                 uri: 'Uri',
                 symtable: 'SymTable',
                 stage: Stage = Stage.PreParse):
        self.uri = uri
        self.stage = stage

        self.symtable = symtable
        self.ast: Optional[ast.AST] = None

        self.module_temp = TypeModuleTemp(uri, self.symtable, TpState.OVER)
