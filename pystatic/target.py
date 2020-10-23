import ast
from enum import IntEnum
from typing import TYPE_CHECKING, Optional
from pystatic.typesys import TypeClassTemp, TypeModuleTemp
from pystatic.message import MessageBox

if TYPE_CHECKING:
    from pystatic.symid import SymId
    from pystatic.symtable import SymTable


class Stage(IntEnum):
    """Number ascends as the analysis going deeper"""
    Parse = 1
    Preprocess = 2
    Infer = 3


class BlockTarget:
    """Block target mainly used for function"""
    def __init__(self,
                 symid: 'SymId',
                 symtable: 'SymTable',
                 mbox: MessageBox,
                 stage: Stage = Stage.Parse) -> None:
        self.symid = symid
        self.symtable = symtable
        self.stage = stage
        self.mbox: 'MessageBox' = mbox
        self.ast: Optional[ast.AST] = None


class MethodTarget(BlockTarget):
    def __init__(self,
                 symid: 'SymId',
                 symtable: 'SymTable',
                 clstemp: 'TypeClassTemp',
                 astnode: 'ast.AST',
                 mbox: 'MessageBox',
                 stage: Stage = Stage.Preprocess) -> None:
        super().__init__(symid, symtable, mbox, stage)
        self.clstemp = clstemp
        self.ast = astnode


class Target(BlockTarget):
    """Module level block target"""
    def __init__(self,
                 symid: 'SymId',
                 symtable: 'SymTable',
                 mbox: 'MessageBox',
                 path: str,
                 stage: Stage = Stage.Parse):
        super().__init__(symid, symtable, mbox, stage)
        # NOTE: TpStage.OVER may be wrong.
        self.module_temp = TypeModuleTemp(symid, self.symtable)
        self.path: str = path  # type: ignore
