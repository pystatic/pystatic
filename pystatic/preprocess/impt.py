"""
Resovle import related type information.

This module will add attribute '_import_info_cache' to symtable to avoid modify
'import_info' attribute of the symtable.
"""

import ast
from pystatic.typesys import TypeClassTemp, TypeModuleTemp, TypeType
from typing import TYPE_CHECKING, Union, Tuple, List, Dict, Any
from pystatic.uri import rel2absuri, Uri, uri2list
from pystatic.symtable import SymTable, Entry
from pystatic.typesys import any_ins, TypeIns
from pystatic.preprocess.sym_util import (fake_imp_entry, add_uri_symtable,
                                          search_uri_symtable,
                                          analyse_import_stmt)

if TYPE_CHECKING:
    from pystatic.preprocess.main import Preprocessor


def resolve_import_type(symtable: SymTable, worker: 'Preprocessor'):
    """Resolve types(class definition) imported from other module"""
    new_import_info = {}
    for impt_node in symtable._import_nodes:
        info_list = analyse_import_stmt(impt_node, symtable.glob_uri)

        if isinstance(impt_node, ast.Import):
            for info in info_list:
                uri = info.uri
                asname = info.asname
                add_uri_symtable(symtable, info.uri, worker)
                module_ins = search_uri_symtable(symtable, uri)

                assert module_ins, "module not found error not handled yet"

                if asname == uri:
                    assert uri2list(uri)
                    top_uri = uri2list(uri)[0]

                    if top_uri not in symtable.local:
                        top_module_ins = search_uri_symtable(symtable, top_uri)
                        assert top_module_ins, "module not found error not handled yet"
                        symtable.local[top_uri] = Entry(
                            top_module_ins, impt_node)
                else:
                    symtable.local[asname] = Entry(module_ins, impt_node)

        else:
            new_info = []
            for info in info_list:
                uri = info.uri
                asname = info.asname
                origin_name = info.origin_name

                is_module = _resolve_import_chain(symtable, asname, worker,
                                                  True)
                if not is_module:
                    new_info.append((asname, origin_name, impt_node))

                if new_info:
                    new_import_info[uri] = new_info

    assert not hasattr(symtable, '_import_info_cache')
    setattr(symtable, '_import_info_cache', new_import_info)

    for tp_def in symtable._cls_defs.values():
        assert isinstance(tp_def, TypeClassTemp)
        inner_symtable = tp_def.get_inner_symtable()
        resolve_import_type(inner_symtable, worker)


def resolve_import_ins(symtable: SymTable, worker: 'Preprocessor'):
    new_import_info = {}

    assert hasattr(symtable,
                   '_import_info_cache'), "_import_info_cache not set"
    target_import_info = getattr(symtable, '_import_info_cache', None)

    for uri, info in target_import_info.items():
        new_info = []
        for name, origin_name, defnode in info:
            is_module = _resolve_import_chain(symtable, name, worker, False)
            if not is_module:
                new_info.append((name, origin_name, defnode))

        if new_info:
            new_import_info[uri] = new_info

    assert hasattr(symtable, '_import_info_cache')
    delattr(symtable, '_import_info_cache')

    for tp_def in symtable._cls_defs.values():
        assert isinstance(tp_def, TypeClassTemp)
        inner_symtable = tp_def.get_inner_symtable()
        resolve_import_ins(inner_symtable, worker)


def _resolve_import_chain(symtable: 'SymTable', name: str,
                          worker: 'Preprocessor', is_type: bool) -> bool:
    """Resolve type from an import chaine

    - is_type is True:
        Return true if it truly stands for an type temp.
    - is_type is False:
        Return true if the type is found.
    """
    imp_entry: Any = symtable.lookup_entry(name)

    if not isinstance(imp_entry, fake_imp_entry):
        return False

    cur_state = (imp_entry.uri, imp_entry.origin_name)

    state_set = set()  # (uri, origin_name)
    buf_targets: List[Tuple['SymTable', str]] = [(symtable, name)]
    result: Any = None

    while True:
        if cur_state in state_set:
            # FIXME: import loop, eliminate loop and warning here
            return False
        mod_uri = cur_state[0]  # module uri
        name_in_mod = cur_state[1]  # name in the current module
        state_set.add(cur_state)

        module_temp = worker.get_module_temp(mod_uri)
        # TODO: warning here
        assert isinstance(
            module_temp, TypeModuleTemp
        ), "this test may fail because the module can't be found, I'll instead warning in the future"

        cur_symtable = module_temp.get_inner_symtable()

        cur_entry: Any = cur_symtable.lookup_local_entry(name_in_mod)
        if cur_entry:
            if isinstance(cur_entry, fake_imp_entry):
                # indirect import
                cur_state = (cur_entry.uri, cur_entry.origin_name)
                buf_targets.append((cur_symtable, name_in_mod))
            elif isinstance(cur_entry, Entry):
                tpins = cur_entry.get_type()

                if not tpins:
                    # is_type is True: the imported symbol is not a class temp
                    # is_type is False: the symbol is not found
                    # TODO: warning here
                    return False

                if is_type:
                    if isinstance(tpins, TypeType):
                        result = tpins  # find the final TypeTemp
                        break
                else:
                    assert isinstance(tpins, TypeIns)
                    result = tpins
                    break
            else:
                return False  # fake_entry(not a class definition)
        else:
            result = None  # not found
            break

    if result:
        if is_type:
            for target_symtable, target_name in buf_targets:
                assert isinstance(target_symtable, SymTable)
                entry: Any = target_symtable.lookup_local_entry(target_name)
                assert isinstance(entry, fake_imp_entry)
                new_entry = Entry(result, entry.defnode)
                target_symtable.local[
                    name] = new_entry  # avoid possible name collision test
            return True
        else:
            for target_symtable, target_name in buf_targets:
                assert isinstance(target_symtable, SymTable)
                entry: Any = target_symtable.lookup_local_entry(target_name)
                assert isinstance(entry, fake_imp_entry)
                new_entry = Entry(result, entry.defnode)
                target_symtable.local[name] = new_entry
            return True
    else:
        # result is None implies not found
        # TODO: warning here
        for target_symtable, target_name in buf_targets:
            assert isinstance(target_symtable, SymTable)
            entry: Any = target_symtable.lookup_local_entry(target_name)
            assert isinstance(entry, fake_imp_entry)
            new_entry = Entry(any_ins, entry.defnode)
            target_symtable.local[name] = new_entry  # same as above
        return False
