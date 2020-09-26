import enum
import ast
from pystatic import symtable
from typing import TYPE_CHECKING, Optional
from pystatic.typesys import TypeModuleTemp, TpState

if TYPE_CHECKING:
    from pystatic.uri import Uri
    from pystatic.symtable import SymTable


class Stage(enum.IntEnum):
    """Number ascends as the analysis going deeper"""
    PreParse = 0
    PreSymtable = 1


class BlockTarget:
    """Block target mainly used for function"""
    def __init__(self,
                 uri: 'Uri',
                 symtable: 'SymTable',
                 stage: Stage = Stage.PreParse) -> None:
        self.uri = uri
        self.symtable = symtable
        self.stage = stage
        self.ast: Optional[ast.AST] = None


class Target(BlockTarget):
    """Module level block target"""
    def __init__(self,
                 uri: 'Uri',
                 symtable: 'SymTable',
                 stage: Stage = Stage.PreParse):
        super().__init__(uri, symtable, stage)
        # NOTE: TpStage.OVER may be wrong.
        self.module_temp = TypeModuleTemp(uri, self.symtable, TpState.OVER)
