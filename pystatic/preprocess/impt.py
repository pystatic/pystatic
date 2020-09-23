import ast
from typing import TYPE_CHECKING, Union, Tuple, List, Dict
from pystatic.uri import uri_last, uri_parent, rel2absuri, Uri
from pystatic.symtable import SymTable, Entry

if TYPE_CHECKING:
    from pystatic.manager import Manager


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


def resolve_import_type(symtable: SymTable, manager: 'Manager'):
    for uri, info in symtable.import_info.items():
        module_temp = manager.get_module_temp(uri)
        if not module_temp:
            assert 0, "this error not handled yet"  # TODO: add warning here

        for name, origin_name in info:
            entry = symtable.lookup_local_entry(name)
            assert entry
            if not origin_name:
                # the module itself
                entry.set_type(module_temp.get_default_type())
            else:
                cls_temp = module_temp.get_type_def(origin_name)
                if cls_temp:
                    entry.set_type(cls_temp.get_default_type())
                else:
                    pass  # TODO: add warning here
