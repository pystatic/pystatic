import ast
from typing import TYPE_CHECKING
from collections import deque
from typing import TYPE_CHECKING, Deque, List
from pystatic.preprocess.definition import (get_definition,
                                            get_definition_in_method)
from pystatic.preprocess.impt import resolve_import_type, resolve_import_ins
from pystatic.preprocess.cls import (resolve_cls_def, resolve_cls_method,
                                     resolve_cls_attr)
from pystatic.preprocess.local import resolve_local_typeins, resolve_local_func
from pystatic.target import BlockTarget, MethodTarget, Target, Stage

if TYPE_CHECKING:
    from pystatic.manager import Manager


class ReadNsAst(Exception):
    pass


def path2ast(path: str) -> ast.AST:
    """May throw FileNotFoundError or SyntaxError"""
    with open(path, 'r') as f:
        content = f.read()
        return ast.parse(content, type_comments=True)


class Preprocessor:
    def __init__(self, manager: 'Manager') -> None:
        self.manager = manager
        # dequeue that store targets waiting for get definitions in them
        self.q_parse: Deque[BlockTarget] = deque()

    def add_to_process_queue(self, target: BlockTarget):
        self.q_parse.append(target)

    def process(self):
        self._deal()

    def _deal(self):
        to_check: List[BlockTarget] = []
        while len(self.q_parse) > 0:
            current = self.q_parse[0]
            self.q_parse.popleft()
            assert current.stage == Stage.Preprocess
            assert current.ast
            to_check.append(current)

            # get current module's class definitions.
            if isinstance(current, MethodTarget):
                get_definition_in_method(current, self.manager, current.mbox)
            else:
                get_definition(current, self.manager, current.mbox)

        # get type imported from other module.
        for target in to_check:
            resolve_import_type(target.symtable, self.manager)

        resolve_cls_def(to_check, self.manager)

        # from now on, all valid types in the module should be correctly
        # identified because possible type(class) information is collected.
        for target in to_check:
            resolve_local_typeins(target.symtable, target.mbox)
            resolve_local_func(target.symtable, target.mbox)

        for target in to_check:
            resolve_import_ins(target.symtable, self.manager)

        for target in to_check:
            resolve_cls_method(target.symtable, target.symid, self.manager,
                               target.mbox)
            resolve_cls_attr(target.symtable, target.mbox)

            if isinstance(target, Target):
                target.stage = Stage.Infer
