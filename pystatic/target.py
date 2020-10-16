import enum
import ast
from pystatic.option import Option
from pystatic import symtable
from typing import TYPE_CHECKING, Optional
from pystatic.typesys import TypeClassTemp, TypeModuleTemp, TpState

if TYPE_CHECKING:
    from pystatic.uri import Uri
    from pystatic.symtable import SymTable
    from pystatic.message import MessageBox


class Stage(enum.IntEnum):
    """Number ascends as the analysis going deeper"""
    PreParse = 0
    PreSymtable = 1
    Processed = 2


class BlockTarget:
    """Block target mainly used for function"""
    def __init__(self,
                 uri: 'Uri',
                 symtable: 'SymTable',
                 mbox: Optional[MessageBox] = None,
                 stage: Stage = Stage.PreParse) -> None:
        self.uri = uri
        self.symtable = symtable
        self.stage = stage
        self.mbox: 'MessageBox' = mbox  # type: ignore
        self.ast: Optional[ast.AST] = None


class MethodTarget(BlockTarget):
    def __init__(self,
                 uri: 'Uri',
                 symtable: 'SymTable',
                 clstemp: 'TypeClassTemp',
                 astnode: 'ast.AST',
                 mbox: 'MessageBox',
                 stage: Stage = Stage.PreParse) -> None:
        super().__init__(uri, symtable, mbox, stage)
        self.clstemp = clstemp
        self.ast = astnode


class Target(BlockTarget):
    """Module level block target"""
    def __init__(self,
                 uri: 'Uri',
                 symtable: 'SymTable',
                 mbox: Optional['MessageBox'] = None,
                 path: Optional[str] = None,
                 stage: Stage = Stage.PreParse):
        super().__init__(uri, symtable, mbox, stage)
        # NOTE: TpStage.OVER may be wrong.
        self.module_temp = TypeModuleTemp(uri, self.symtable)
        self.path: str = path  # type: ignore
