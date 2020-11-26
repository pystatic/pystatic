import ast
from collections import deque
from typing import TYPE_CHECKING, List, Deque
from pystatic.target import BlockTarget, MethodTarget, Stage, Target
from pystatic.preprocess.definition import (get_definition,
                                            get_definition_in_method)
from pystatic.preprocess.prepinfo import PrepEnvironment, PrepDef, PrepInfo
from pystatic.preprocess.dependency import toposort_prepdef
from pystatic.preprocess.resolve import resolve, resolve_import, resolve_cls_method

if TYPE_CHECKING:
    from pystatic.manager import Manager


def dump_to_symtable(target: 'BlockTarget', env: 'PrepEnvironment'):
    init_prepinfo = env.get_target_prepinfo(target)
    assert init_prepinfo
    queue: Deque[PrepInfo] = deque()
    queue.append(init_prepinfo)

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
                    get_definition_in_method(current, self.env, current.mbox)
                else:
                    get_definition(current, self.env, current.mbox)

            prepinfo_list = [
                prepinfo for target in to_check if (prepinfo := self.env.get_target_prepinfo(target))
            ]
            assert len(prepinfo_list) == len(to_check)

            # get type imported from other module.
            for prepinfo in prepinfo_list:
                resolve_import(prepinfo, self.env)

            resolve_order = toposort_prepdef(prepinfo_list)
            resolve(resolve_order)

            for target in to_check:
                resolve_cls_method(target, self.env, target.mbox)
                dump_to_symtable(target, self.env)

            for target in to_check:
                if isinstance(target, Target) and manager.is_on_check(
                        target.symid):
                    manager.update_stage(target, Stage.Infer)
