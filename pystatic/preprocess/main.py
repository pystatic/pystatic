import ast
from collections import deque
from pystatic.preprocess.resolve_cls import resolve_cls_placeholder
from pystatic.preprocess.resolve_spt import resolve_spt
from typing import TYPE_CHECKING, List, Deque
from pystatic.target import BlockTarget, FunctionTarget, MethodTarget, Stage, Target
from pystatic.preprocess.definition import (get_definition,
                                            get_definition_in_method,
                                            get_definition_in_function)
from pystatic.preprocess.dependency import toposort_prepdef
from pystatic.preprocess.resolve import resolve, resolve_import, resolve_cls_method
from pystatic.preprocess.prepinfo import *

if TYPE_CHECKING:
    from pystatic.manager import Manager


def dump_to_symtable(prepinfo: 'PrepInfo', env: 'PrepEnvironment'):
    queue: Deque[PrepInfo] = deque()
    queue.append(prepinfo)

    while len(queue):
        cur_prepinfo = queue.popleft()
        cur_prepinfo.dump()

        for clsdef in cur_prepinfo.cls.values():
            queue.append(clsdef.prepinfo)

class Preprocessor:
    def __init__(self, manager: 'Manager') -> None:
        self.env = PrepEnvironment(manager)

    def process(self):
        manager = self.env.manager
        while len(manager.q_preprocess) > 0:
            to_check: List[BlockTarget] = []
            while len(manager.q_preprocess) > 0:
                current = manager.q_preprocess[0]
                manager.q_preprocess.popleft()
                assert current.stage == Stage.Preprocess
                assert current.ast
                to_check.append(current)

                # get current module's class definitions.
                if isinstance(current, MethodTarget):
                    get_definition_in_method(current, self.env)
                elif isinstance(current, FunctionTarget):
                    get_definition_in_function(current, self.env)
                else:
                    get_definition(current, self.env)

            prepinfo_list = [
                prepinfo for target in to_check if (prepinfo := self.env.get_target_prepinfo(target))
            ]
            assert len(prepinfo_list) == len(to_check)

            # get type imported from other module.
            for prepinfo in prepinfo_list:
                resolve_import(prepinfo, self.env)

            resolve_order = toposort_prepdef(prepinfo_list)
            resolve(resolve_order)

            for prepdef in resolve_order:
                if isinstance(prepdef, prep_cls):
                    resolve_cls_placeholder(prepdef, prepdef.def_prepinfo.mbox)

            for prepinfo in prepinfo_list:
                resolve_cls_method(prepinfo, self.env, prepinfo.mbox)
                resolve_spt(prepinfo, self.env)
                dump_to_symtable(prepinfo, self.env)

            for target in to_check:
                if isinstance(target, Target) and manager.is_on_check(
                        target.symid):
                    manager.update_stage(target, Stage.Infer)
        self.env.clear()
