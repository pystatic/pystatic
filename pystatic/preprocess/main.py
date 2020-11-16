import ast
from typing import TYPE_CHECKING, List
from pystatic.preprocess.definition import (get_definition,
                                            get_definition_in_method)
from pystatic.preprocess.impt import resolve_import
from pystatic.preprocess.cls import (dump_to_symtable, resolve_cls_dependency,
                                     resolve_cls_inheritence,
                                     resolve_cls_method)
from pystatic.preprocess.local import resolve_local_typeins, resolve_local_func
from pystatic.preprocess.prepinfo import PrepEnvironment
from pystatic.target import BlockTarget, MethodTarget, Stage

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
        self.env = PrepEnvironment(manager)

    def process(self):
        while len(self.manager.q_preprocess) > 0:
            to_check: List[BlockTarget] = []
            while len(self.manager.q_preprocess) > 0:
                current = self.manager.q_preprocess[0]
                self.manager.q_preprocess.popleft()
                assert current.stage == Stage.Preprocess
                assert current.ast
                to_check.append(current)

                # get current module's class definitions.
                if isinstance(current, MethodTarget):
                    get_definition_in_method(current, self.env, current.mbox)
                else:
                    get_definition(current, self.env, current.mbox)

            # get type imported from other module.
            for target in to_check:
                resolve_import(target, self.env)

            cls_resolve_order = resolve_cls_dependency(to_check, self.env)
            for clsdef in cls_resolve_order:
                temp_mbox = self.env.manager.get_mbox_by_symid(
                    clsdef.clstemp.module_symid)
                assert temp_mbox, "This should always true because pystatic must have added the mbox before"
                resolve_cls_inheritence(clsdef, temp_mbox)

            # from now on, all valid types in the module should be correctly
            # identified because possible type(class) information is collected.
            for target in to_check:
                resolve_local_func(target, self.env, target.mbox)
                resolve_local_typeins(target, self.env, target.mbox)

            # for target in to_check:
            #     resolve_import_ins(target.symtable, self.manager)

            for target in to_check:
                resolve_cls_method(target, self.env, target.mbox)

                # if isinstance(target, Target):
                #     self.manager.update_stage(target, Stage.Infer)

            for target in to_check:
                dump_to_symtable(target, self.env)
            pass
