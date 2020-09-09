import os
from pystatic.config import PY_VERSION
from typing import List, Dict, Optional, Union, TYPE_CHECKING
from pystatic.util import uri2list, absolute_urilist, list2uri

if TYPE_CHECKING:
    from pystatic.typesys import TypeModuleTemp
    from pystatic.config import PY_VERSION


class ModuleFindRes:
    Module = 1
    Package = 2
    Namespace = 3

    def __init__(self, res_type: int, paths: List[str],
                 target_file: Optional[str]) -> None:
        self.res_type = res_type
        # For package to set correct paths attribute
        self.paths = paths
        # File to analyse, if result is a namespace package, target_file is None
        self.target_file = target_file


class Node:
    def __init__(self, res: ModuleFindRes):
        self.res: ModuleFindRes = res
        self.child: Dict[str, Node] = {}


class ModuleFinder:
    """PEP 561

    - Stubs or Python source manually put at the beginning of the path($MYPYPATH)
    - User code - files the type checker is running on.
    - Stub packages.
    - Inline packages.
    - Typeshed.
    """
    def __init__(self, manual_path: List[str], user_path: List[str],
                 sitepkg: List[str], typeshed: Optional[str],
                 py_version: PY_VERSION):
        self.manual_path = manual_path
        self.user_path = user_path
        self.sitepkg = sitepkg
        self.typeshed = typeshed
        self.search_path = manual_path + user_path + sitepkg
        if typeshed:
            self.search_path += _resolve_typeshed(typeshed, py_version)

        # dummy namespace on the root
        dummy_ns = ModuleFindRes(ModuleFindRes.Namespace, self.search_path,
                                 None)
        self.root = Node(dummy_ns)

    def find(self, uri: str) -> Optional[ModuleFindRes]:
        urilist = uri2list(uri)
        if not urilist:
            return None

        cur_node = self.root
        i = 0
        while i < len(urilist) and urilist[i] in cur_node.child:
            cur_node = cur_node.child[urilist[i]]
            i += 1

        cur_res = cur_node.res
        for suburi in urilist[i:]:
            if cur_res.res_type == ModuleFindRes.Module:
                return None
            walk_res = _walk_single(suburi, cur_res.paths)
            if not walk_res:
                return None
            cur_res = walk_res

        return cur_res

    def relative_find(self, uri: str,
                      module: 'TypeModuleTemp') -> Optional[ModuleFindRes]:
        abs_uri = urilist_from_impitem(uri, module)
        return self.find(list2uri(abs_uri))


def _walk_single(suburi: str, paths: List[str]) -> Optional[ModuleFindRes]:
    assert paths
    ns_paths = []
    target = None
    target_file = None
    for path in paths:
        sub_target = os.path.normpath(os.path.join(path, suburi))
        pyi_file = sub_target + '.pyi'
        py_file = sub_target + '.py'
        if os.path.isfile(pyi_file):
            return ModuleFindRes(ModuleFindRes.Module, [pyi_file], pyi_file)
        if os.path.isfile(py_file):
            return ModuleFindRes(ModuleFindRes.Module, [py_file], py_file)

        if os.path.isdir(sub_target):
            init_file = os.path.join(sub_target, '__init__.py')
            if os.path.isfile(init_file):
                target = sub_target
                target_file = init_file
            else:
                ns_paths.append(sub_target)
    if target:
        assert target_file
        return ModuleFindRes(ModuleFindRes.Package, [target], target_file)
    elif ns_paths:
        return ModuleFindRes(ModuleFindRes.Namespace, ns_paths, None)
    else:
        return None


def _resolve_typeshed(typeshed: str, pyv: PY_VERSION) -> List[str]:
    stdlib_res = []
    third_party_res = []

    stdlib = os.path.join(typeshed, 'stdlib')
    third_party = os.path.join(typeshed, 'third_party')
    major_pyv_str = str(pyv[0])
    pyv_str = str(pyv[0]) + '.' + str(pyv[1])

    if os.path.isdir(stdlib):
        specific_dir = os.path.join(stdlib, pyv_str)
        major_dir = os.path.join(stdlib, major_pyv_str)
        two_or_three = os.path.join(stdlib, '2and3')
        for curdir in [specific_dir, major_dir, two_or_three]:
            if os.path.isdir(curdir):
                stdlib_res.append(curdir)

    if os.path.isdir(third_party):
        specific_dir = os.path.join(third_party, pyv_str)
        major_dir = os.path.join(third_party, major_pyv_str)
        two_or_three = os.path.join(third_party, '2and3')
        for curdir in [specific_dir, major_dir, two_or_three]:
            if os.path.isdir(curdir):
                third_party_res.append(curdir)

    print(stdlib_res + third_party_res)

    return stdlib_res + third_party_res


def uri_from_impitem(uri: str, curmodule: 'TypeModuleTemp') -> str:
    return list2uri(urilist_from_impitem(uri, curmodule))


def urilist_from_impitem(uri: str, curmodule: 'TypeModuleTemp') -> List[str]:
    package = uri2list(curmodule.uri)[:-1]  # the package that cur_module in
    return absolute_urilist(uri, list2uri(package))
