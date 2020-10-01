"""
Resovle import related type information.

This module will add attribute '_import_info_cache' to symtable to avoid modify
'import_info' attribute of the symtable.
"""

import ast
from pystatic.typesys import TypeClassTemp, TypeModuleTemp, TypeType
from typing import TYPE_CHECKING, Union, Tuple, List, Dict, Any
from pystatic.uri import rel2absuri, Uri
from pystatic.symtable import SymTable, Entry
from pystatic.typesys import any_ins, TypeIns
from pystatic.preprocess.sym_util import fake_imp_entry, add_uri_symtable

if TYPE_CHECKING:
    from pystatic.preprocess.main import Preprocessor


def split_import_stmt(node: Union[ast.Import, ast.ImportFrom],
                      uri: Uri) -> Dict[Uri, List[Tuple[str, str]]]:
    """Return: imported Moduri mapped to (name1, name2) where name1 is the name in the
    current module and name2 is the name in the imported module.
    """
    res = {}
    if isinstance(node, ast.Import):
        for alias in node.names:
            module_uri = alias.name
            as_name = alias.asname or module_uri
            res.setdefault(module_uri, []).append(
                (as_name, ''))  # empty string means the module itself

    elif isinstance(node, ast.ImportFrom):
        imp_name = '.' * node.level
        imp_name += node.module or ''
        module_uri = rel2absuri(uri, imp_name)
        imported = []
        for alias in node.names:
            attr_name = alias.name
            as_name = alias.asname or attr_name
            imported.append((as_name, attr_name))
        res = {module_uri: imported}

    else:
        raise TypeError("node doesn't stand for an import statement")

    return res


def resolve_import_type(symtable: SymTable, worker: 'Preprocessor'):
    """Resolve types(class definition) imported from other module"""
    new_import_info = {}
    for module_uri, nodelist in symtable._import_info.items():
        module_temp = add_uri_symtable(symtable, module_uri, worker)

        # module_temp = worker.get_module_temp(module_uri)
        # module_temp = search_uri_symtable(symtable, module_uri)
        assert module_temp, "module not found error not handled yet"  # TODO: add warning here

        new_info = []
        for defnode in nodelist:
            assert isinstance(defnode, ast.ImportFrom) or isinstance(
                defnode, ast.Import)
            imp_dict = split_import_stmt(defnode, symtable.glob_uri)

            for uri, tples in imp_dict.items():
                for asname, origin_name in tples:
                    if not origin_name:
                        # the module itself
                        entry: Any = symtable.local.get(asname)
                        assert entry and not isinstance(entry,
                                                        Entry)  # not complete
                        module_type = module_temp.get_default_type()
                        symtable.local[asname] = Entry(module_type.getins(),
                                                       defnode)
                    else:
                        is_module = _resolve_import_chain(
                            symtable, asname, worker, True)
                        if not is_module:
                            new_info.append((asname, origin_name, defnode))

        if new_info:
            new_import_info[module_uri] = new_info

    # set up _import_info_cache, this should be the first function called
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
        module_temp = worker.get_module_temp(uri)
        assert module_temp, "module not found error not handled yet"  # TODO: add warning here

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
