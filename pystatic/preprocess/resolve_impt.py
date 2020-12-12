from collections import deque
from typing import List, Deque
from pystatic.preprocess.util import update_symtable_import_cache
from pystatic.preprocess.prepinfo import *


def resolve_import(prepinfo: "PrepInfo", env: "PrepEnvironment"):
    queue: Deque["PrepInfo"] = deque()
    queue.append(prepinfo)

    while len(queue):
        cur_prepinfo = queue.popleft()
        symtable = cur_prepinfo.symtable
        for _, entry in cur_prepinfo.impt.items():
            update_symtable_import_cache(symtable, entry, env.manager)
            if not entry.origin_name:
                # import <module_name>
                module_ins = env.manager.get_module_ins(entry.symid)
                if module_ins:
                    module_prepinfo = env.get_prepinfo(entry.symid)
                    if module_prepinfo:
                        # used for eval_expr because new symbols haven't been
                        # added to module instance yet.
                        module_ins.set_consultant(module_prepinfo)
                    entry.value = module_ins
                else:
                    # TODO: error: module not found
                    entry.value = None

            elif not entry.value:
                asname = entry.asname
                assert asname
                _resolve_import_chain(cur_prepinfo, asname, env)

        for clsdef in cur_prepinfo.cls.values():
            queue.append(clsdef.prepinfo)


def _resolve_import_chain(prepinfo: "PrepInfo", name: str, env: "PrepEnvironment"):
    """Resolve type from an import chaine"""
    impt_entry = prepinfo.impt[name]
    cur_state = (impt_entry.symid, impt_entry.origin_name)
    state_set = set()  # (symid, origin_name)
    buf_targets: List[prep_impt] = [impt_entry]
    result = None

    while True:
        if cur_state in state_set:
            # TODO: error: import loop
            raise NotImplementedError("import loop")

        mod_symid = cur_state[0]  # module symid
        name_in_mod = cur_state[1]  # name in the current module
        state_set.add(cur_state)

        lookup_res = env.lookup(mod_symid, name_in_mod)
        if lookup_res:
            if isinstance(lookup_res, prep_impt):
                if lookup_res.value:
                    result = lookup_res.value
                    break
                else:
                    cur_state = (lookup_res.symid, lookup_res.origin_name)
                    buf_targets.append(lookup_res)
            else:
                result = lookup_res
                break
        else:
            result = None
            break

    if result:
        for cur_impt in buf_targets:
            assert isinstance(cur_impt, prep_impt)
            cur_impt.value = result
        return True
    else:
        # result is None implies nothing found
        # TODO: warning here
        return False
