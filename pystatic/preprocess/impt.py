"""
Resovle import related type information.
"""

import ast
from pystatic.typesys import TypeClassTemp, TypeModuleTemp, TypeTemp, TypeType
from typing import Optional, TYPE_CHECKING, Union, Tuple, List, Dict, Any
from pystatic.uri import uri_last, uri_parent, rel2absuri, Uri
from pystatic.symtable import SymTable, Entry
from pystatic.typesys import any_ins
from pystatic.preprocess.sym_util import fake_imp_entry

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
    for uri, info in symtable._import_info.items():
        module_temp = worker.get_module_temp(uri)
        assert module_temp, "module not found error not handled yet"  # TODO: add warning here

        new_info = []
        for name, origin_name, defnode in info:
            is_module = _resolve_import_type_chain(symtable, name, worker)
            if not is_module:
                new_info.append((name, origin_name, defnode))

        if new_info:
            new_import_info[uri] = new_info

    symtable._import_info = new_import_info

    for tp_def in symtable._cls_defs.values():
        assert isinstance(tp_def, TypeClassTemp)
        inner_symtable = tp_def.get_inner_symtable()
        resolve_import_type(inner_symtable, worker)


def _resolve_import_type_chain(symtable: 'SymTable', name: str,
                               worker: 'Preprocessor') -> bool:
    """Resolve type from an import chaine

    Return true if it truly stands for an module
    """
    imp_entry: Any = symtable.lookup_entry(name)

    if not isinstance(imp_entry, fake_imp_entry):
        return False

    cur_state = (imp_entry.uri, imp_entry.origin_name)

    state_set = set()  # (uri, origin_name)
    buf_targets = [(symtable, name)]
    result: Optional[TypeTemp] = None

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
        ), "this test may fail because the module can't be found, I'll instead warning will in the future"

        cur_symtable = module_temp.get_inner_symtable()

        cur_entry: Any = cur_symtable.lookup_local_entry(name_in_mod)
        if cur_entry:
            if isinstance(cur_entry, fake_imp_entry):
                # indirect import
                cur_state = (cur_entry.uri, cur_entry.origin_name)
                buf_targets.append((cur_symtable, name_in_mod))
            else:
                assert isinstance(cur_entry, Entry)
                tpins = cur_entry.get_type()
                assert tpins
                if isinstance(tpins, TypeType):
                    result = tpins.temp  # find the final TypeTemp!!!
                    assert isinstance(result, TypeTemp)
                    break
        else:
            result = None  # not found
            break

    if result:
        for target_symtable, target_name in buf_targets:
            assert isinstance(target_symtable, SymTable)
            entry: Any = target_symtable.lookup_local_entry(target_name)
            assert isinstance(entry, fake_imp_entry)
            new_entry = Entry(result.get_default_type(), entry.defnode)
            target_symtable.local[
                name] = new_entry  # avoid possible name collision test
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
