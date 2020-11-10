import ast
from enum import IntEnum, Enum, auto
from typing import TYPE_CHECKING, Optional
from pystatic.typesys import TypeClassTemp
from pystatic.predefined import TypeModuleTemp
from pystatic.message import MessageBox

if TYPE_CHECKING:
    from pystatic.symid import SymId
    from pystatic.symtable import SymTable


class Stage(IntEnum):
    """Number ascends as the analysis going deeper"""
    Parse = 1
    Preprocess = 2
    Infer = 3
    FINISH = 4


class BlockTarget:
    """Block target mainly used for function"""
    def __init__(self,
                 symid: 'SymId',
                 symtable: 'SymTable',
                 mbox: MessageBox,
                 stage: Stage = Stage.Preprocess) -> None:
        self.symid = symid
        self.symtable = symtable
        self.mbox: 'MessageBox' = mbox
        self.ast: Optional[ast.AST] = None
        self.stage = stage


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
        self.path: str = path

    @property
    def analyse_path(self):
        return self.path


class PackageTarget(Target):
    def __init__(self,
                 symid: 'SymId',
                 symtable: 'SymTable',
                 mbox: 'MessageBox',
                 path: str,
                 analyse_path: str,
                 stage: Stage = Stage.Parse):
        super().__init__(symid, symtable, mbox, path, stage)
        self.__analyse_path = analyse_path

    @property
    def analyse_path(self):
        return self.__analyse_path
