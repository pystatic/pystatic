from collections import deque
from typing import List, Deque
from pystatic.symid import SymId, rel2abssymid, symid_parent, absolute_symidlist
from pystatic.preprocess.prepinfo import *
from pystatic.predefined import *


def resolve_import(prepinfo: "PrepInfo", env: "PrepEnvironment"):
    queue: Deque["PrepInfo"] = deque()
    queue.append(prepinfo)

    while len(queue):
        cur_prepinfo = queue.popleft()
        symtable = cur_prepinfo.symtable
        tmp_impt = {**cur_prepinfo.impt}  # copy of cur_prepinfo.impt
        for _, entry in tmp_impt.items():
            update_symtable_import_cache(symtable, cur_prepinfo, entry, env.manager)
            if not entry.origin_name:
                # import <module_name>
                module_ins = env.manager.get_module_ins(entry.symid)
                if module_ins:
                    module_prepinfo = env.get_prepinfo(entry.symid)
                    if module_prepinfo:
                        # used for infer_expr because new symbols haven't been
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
            return
            raise NotImplementedError("import loop")

        mod_symid = cur_state[0]  # module symid
        name_in_mod = cur_state[1]  # name in the current module
        state_set.add(cur_state)

        lookup_res = env.lookup(mod_symid, name_in_mod, True)
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


def update_symtable_import_cache(
    symtable: "SymTable", prepinfo: "PrepInfo", entry: "prep_impt", manager: "Manager"
) -> Optional[TypeIns]:
    def set_prepinfo_impt(symid: SymId, moduleins: TypeModuleIns):
        if (cur_impt := prepinfo.impt.get(symid)) :
            if cur_impt.origin_name == "":
                cur_impt.value = moduleins
        else:
            prepinfo.impt[symid] = prep_impt(
                symid, "", symid, entry.def_prepinfo, entry.defnode
            )
            prepinfo.impt[symid].value = moduleins

    symid = entry.symid

    symidlist = absolute_symidlist(symtable.glob_symid, symid)
    if not symidlist:
        return None

    cache = symtable.import_cache

    # get the initial module ins or package ins
    cur_symid = symidlist[0]
    cur_ins = cache.get_module_ins(cur_symid)

    if not cur_ins:
        cur_ins = manager.get_module_ins(cur_symid)
        if cur_ins is None:
            return None
        else:
            cache.set_moduleins(cur_symid, cur_ins)

    assert isinstance(cur_ins, TypeModuleIns)
    for i in range(1, len(symidlist)):
        if not isinstance(cur_ins, TypePackageIns):
            return None

        set_prepinfo_impt(cur_symid, cur_ins)

        cur_symid += f".{symidlist[i]}"
        if symidlist[i] not in cur_ins.submodule:
            module_ins = manager.get_module_ins(cur_symid)
            if not module_ins:
                return None

            # FIXME: fix me after modify TypePackageIns
            assert isinstance(module_ins, TypeModuleIns)
            if isinstance(module_ins, TypePackageIns):
                cur_ins.add_submodule(symidlist[i], module_ins)
            else:
                if i != len(symidlist) - 1:
                    return None
                cur_ins.add_submodule(symidlist[i], module_ins)
                return module_ins

        cur_ins = cur_ins.submodule[symidlist[i]]

    assert cur_symid == entry.symid
    set_prepinfo_impt(cur_symid, cur_ins)

    # If the source is a package then another module may be imported.
    # Example:
    # from fruit import apple
    # fruit is a package and apple is a module so pystatic need to add apple
    # to fruit's submodule list
    if isinstance(cur_ins, TypePackageIns):
        if not entry.is_import_module():
            cur_symid += f".{entry.origin_name}"
            module_ins = manager.get_module_ins(cur_symid)

            if module_ins:
                cur_ins.add_submodule(entry.origin_name, module_ins)
                set_prepinfo_impt(cur_symid, module_ins)

    return cur_ins
