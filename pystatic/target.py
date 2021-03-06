import ast
from enum import IntEnum
from typing import TYPE_CHECKING, Optional
from pystatic.typesys import TypeClassTemp
from pystatic.predefined import TypeModuleIns

if TYPE_CHECKING:
    from pystatic.symid import SymId
    from pystatic.symtable import SymTable, FunctionSymTable
    from pystatic.error.errorbox import ErrorBox


class Stage(IntEnum):
    """Number ascends as the analysis going deeper"""

    Parse = 1
    Preprocess = 2
    Infer = 3
    FINISH = 4


class BlockTarget:
    def __init__(
        self,
        symid: "SymId",
        symtable: "SymTable",
        errbox: "ErrorBox",
        stage: Stage = Stage.Preprocess,
    ) -> None:
        self.symid = symid
        self.symtable = symtable
        self.errbox: "ErrorBox" = errbox
        self.ast: Optional[ast.AST] = None
        self.stage = stage


class FunctionTarget(BlockTarget):
    def __init__(
        self,
        symid: "SymId",
        symtable: "FunctionSymTable",
        astnode: "ast.FunctionDef",
        errbox: "ErrorBox",
        stage: Stage = Stage.Preprocess,
    ):
        self.symtable: "FunctionSymTable"
        super().__init__(symid, symtable, errbox, stage)
        self.ast = astnode


class MethodTarget(FunctionTarget):
    def __init__(
        self,
        symid: "SymId",
        symtable: "FunctionSymTable",
        clstemp: "TypeClassTemp",
        astnode: "ast.FunctionDef",
        errbox: "ErrorBox",
        stage: Stage = Stage.Preprocess,
    ) -> None:
        super().__init__(symid, symtable, astnode, errbox, stage)
        self.clstemp = clstemp


class Target(BlockTarget):
    """Module level block target"""

    def __init__(
        self,
        symid: "SymId",
        symtable: "SymTable",
        errbox: "ErrorBox",
        path: str,
        is_special: bool = False,
        stage: Stage = Stage.Parse,
    ):
        """
        @param is_special: If target is builtins or typing, is_special is True,
        otherwise False.
        """
        super().__init__(symid, symtable, errbox, stage)
        # NOTE: TpStage.OVER may be wrong.
        self.module_ins = TypeModuleIns(self.symtable)
        self.path: str = path
        self.is_special = is_special

    @property
    def analyse_path(self):
        return self.path

    def clear(self):
        self.symtable.clear()
        self.errbox.clear()


class PackageTarget(Target):
    def __init__(
        self,
        symid: "SymId",
        symtable: "SymTable",
        errbox: "ErrorBox",
        path: str,
        analyse_path: str,
        stage: Stage = Stage.Parse,
    ):
        super().__init__(symid, symtable, errbox, path, False, stage)
        self.__analyse_path = analyse_path

    @property
    def analyse_path(self):
        return self.__analyse_path
