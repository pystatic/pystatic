"""
Resovle import related type information.
"""

import ast
import copy
from typing import TYPE_CHECKING, Tuple, List, Dict, Optional
from pystatic.typesys import TypeClassTemp, TypeType
from pystatic.predefined import TypeVarIns, TypeModuleTemp
from pystatic.symid import symid2list
from pystatic.symtable import ImportEntry, SymTable
from pystatic.typesys import any_ins, TypeIns
from pystatic.preprocess.prepinfo import *

if TYPE_CHECKING:
    from pystatic.manager import Manager


def resolve_import_type(symtable: SymTable, env: 'PrepEnvironment'):
    """Resolve types(class definition) imported from other module"""
    new_impt_dict: Dict[str, prep_impt] = {}
    fake_data = get_fake_data(symtable)
    cache = symtable.import_cache

    iter_impt = copy.copy(fake_data.impt)

    for _, entry in iter_impt.items():
        impt_node = entry.defnode
        symid = entry.symid
        asname = entry.asname
        origin_name = entry.origin_name

        update_symtable_import_cache(symtable, entry, manager)

        if isinstance(impt_node, ast.Import):
            module_ins = cache.get_moduleins(symid)
            assert module_ins, "module not found error not handled yet"

            if asname == symid:
                # no 'as' in the import statement
                assert symid2list(symid)
                top_symid = symid2list(symid)[0]

                if top_symid not in symtable.local:
                    top_module_ins = cache.get_moduleins(top_symid)
                    assert top_module_ins, "module not found error not handled yet"
                    symtable.import_cache.add_cache(top_symid, '',
                                                    top_module_ins)
                    symtable.add_entry(top_symid,
                                       ImportEntry(top_symid, '', impt_node))
            else:
                symtable.import_cache.add_cache(symid, '', module_ins)
                symtable.add_entry(symid, ImportEntry(symid, '', impt_node))

        else:
            is_type = _resolve_import_chain(symtable, asname, manager, True)
            # if the symbol is not a type or a module, then keep it in the
            # fake_data's impt.
            if not is_type:
                new_impt_dict[asname] = entry

    fake_data.impt = new_impt_dict

    for clsentry in fake_data.cls_def.values():
        tp_temp = clsentry.clstemp
        assert isinstance(tp_temp, TypeClassTemp)
        inner_symtable = tp_temp.get_inner_symtable()
        resolve_import_type(inner_symtable, manager)


def resolve_import_ins(symtable: SymTable, manager: 'Manager'):
    fake_data = get_fake_data(symtable)
    iter_impt = copy.copy(fake_data.impt)

    for _, entry in iter_impt.items():
        asname = entry.asname
        assert asname
        _resolve_import_chain(symtable, asname, manager, False)

    for clsentry in fake_data.cls_def.values():
        tp_temp = clsentry.clstemp
        assert isinstance(tp_temp, TypeClassTemp)
        inner_symtable = tp_temp.get_inner_symtable()
        resolve_import_ins(inner_symtable, manager)


def _resolve_import_chain(symtable: 'SymTable', name: str, manager: 'Manager',
                          is_import_type: bool) -> bool:
    """Resolve type from an import chaine

    is_import_type:
        import a type(class TypeVar ...) or not.

    - is_import_type is True:
        Return true if it truly stands for an type temp or a module temp.
    - is_import_type is False:
        Return true if the type is found.
    """
    fake_data = get_fake_data(symtable)
    impt_entry = fake_data.impt.get(name)
    cur_state = (impt_entry.symid, impt_entry.origin_name)
    state_set = set()  # (symid, origin_name)
    buf_targets: List[Tuple['SymTable', str]] = [(symtable, name)]
    result: Optional['TypeIns'] = None

    while True:
        if cur_state in state_set:
            # FIXME: import loop, eliminate loop and warning here
            assert False, "import loop"

        mod_symid = cur_state[0]  # module symid
        name_in_mod = cur_state[1]  # name in the current module
        state_set.add(cur_state)

        module_temp = manager.get_module_temp(mod_symid)
        # TODO: warning here
        assert isinstance(
            module_temp, TypeModuleTemp
        ), "this test may fail because the module can't be found, I'll instead warning in the future"

        cur_symtable = module_temp.get_inner_symtable()

        tpins = cur_symtable.lookup(name_in_mod)
        if tpins:
            if is_import_type:
                if isinstance(tpins, (TypeType, TypeVarIns)) or isinstance(
                        tpins.temp, TypeModuleTemp):
                    result = tpins  # find the final TypeTemp
                    break
                else:
                    # the symbol is not a type or a module.
                    return False
            else:
                assert isinstance(tpins, TypeIns)
                result = tpins
                break

        else:
            cur_fake_data = try_get_fake_data(cur_symtable)
            flag = False  # find the fake import entry?
            if cur_fake_data:
                cur_entry = cur_fake_data.impt.get(name_in_mod)
                if cur_entry:
                    cur_state = (cur_entry.symid, cur_entry.origin_name)
                    buf_targets.append((cur_symtable, name_in_mod))
                    flag = True

            if not flag:
                result = None
                break

    if result:
        for cur_symtable, name in buf_targets:
            fake_data = try_get_fake_data(cur_symtable)
            assert fake_data, "something went wrong if this test failes"
            assert name in fake_data.impt, "something went wrong if this test failes"

            try:
                origin_entry: fake_impt_entry = fake_data.impt.pop(name)
                module_symid = origin_entry.symid
                origin_name = origin_entry.origin_name
                defnode = origin_entry.defnode
                assert name == origin_entry.asname

                cur_symtable.import_cache.add_cache(module_symid, origin_name,
                                                    result)
                cur_symtable.add_entry(
                    name, ImportEntry(module_symid, origin_name, defnode))
            except KeyError:
                pass

        return True

    else:
        # result is None implies not found
        # TODO: warning here
        for cur_symtable, name in buf_targets:
            try:
                origin_entry: fake_impt_entry = fake_data.impt.pop(name)
                module_symid = origin_entry.symid
                origin_name = origin_entry.origin_name
                defnode = origin_entry.defnode
                assert name == origin_entry.asname

                cur_symtable.import_cache.add_cache(
                    module_symid, origin_name, any_ins)  # default: any_ins
                cur_symtable.add_entry(
                    name, ImportEntry(module_symid, origin_name, defnode))
            except KeyError:
                pass

        return False
