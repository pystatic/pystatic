import os
from pystatic.config import PY_VERSION
from typing import List, Dict, Optional, TYPE_CHECKING
from pystatic.symid import symid2list, absolute_symidlist, list2symid

if TYPE_CHECKING:
    from pystatic.typesys import TypeModuleTemp
    from pystatic.config import PY_VERSION

FilePath = str


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
    def __init__(self, manual_path: List[str], sitepkg: List[str],
                 typeshed: Optional[str], py_version: PY_VERSION):
        self.manual_path = manual_path
        self.user_path = []
        self.sitepkg = sitepkg

        if typeshed:
            self.typeshed = _resolve_typeshed(typeshed, py_version)
        else:
            self.typeshed = []

        # dummy namespace on the root
        self.dummy_ns = ModuleFindRes(ModuleFindRes.Namespace, [], None)
        self.root = Node(self.dummy_ns)

    def add_userpath(self, path: str):
        if path not in self.user_path:
            self.user_path.append(path)

    def find(self, symid: str) -> Optional[ModuleFindRes]:
        symidlist = symid2list(symid)
        if not symidlist:
            return None

        cur_node = self.root
        self.dummy_ns.paths = self.manual_path + self.user_path + self.typeshed + self.sitepkg
        i = 0
        while i < len(symidlist) and symidlist[i] in cur_node.child:
            cur_node = cur_node.child[symidlist[i]]
            i += 1

        cur_res = cur_node.res
        for subsymid in symidlist[i:]:
            if cur_res.res_type == ModuleFindRes.Module:
                return None
            walk_res = _walk_single(subsymid, cur_res.paths)
            if not walk_res:
                return None
            cur_res = walk_res

        return cur_res

    def relative_find(self, symid: str,
                      module: 'TypeModuleTemp') -> Optional[ModuleFindRes]:
        abs_symid = symidlist_from_impitem(symid, module)
        return self.find(list2symid(abs_symid))


def _walk_single(subsymid: str, paths: List[str]) -> Optional[ModuleFindRes]:
    assert paths
    ns_paths = []
    target = None
    target_file = None
    for path in paths:
        sub_target = os.path.normpath(os.path.join(path, subsymid))
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

    return stdlib_res + third_party_res


def symid_from_impitem(symid: str, curmodule: 'TypeModuleTemp') -> str:
    return list2symid(symidlist_from_impitem(symid, curmodule))


def symidlist_from_impitem(symid: str,
                           curmodule: 'TypeModuleTemp') -> List[str]:
    package = symid2list(
        curmodule.symid)[:-1]  # the package that cur_module in
    return absolute_symidlist(list2symid(package), symid)
