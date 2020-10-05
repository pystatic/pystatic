import ast
from typing import List, Tuple, Union, Dict
from pystatic.uri import Uri, rel2absuri


# exception part
class ParseException(Exception):
    """ParseException is used when working on the ast tree however the tree
    doesn't match the structure and the process failed.

    Node points to the position where the process failed.
    Msg is used to describe why it failed(it can be omitted by set it to '').
    """
    def __init__(self, node: ast.AST, msg: str):
        super().__init__(msg)
        self.node = node
        self.msg = msg


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
