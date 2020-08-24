import os
from typing import List, Dict, Optional, Union, TYPE_CHECKING, Tuple
from pystatic.typesys import (TypeModuleTemp, TypePackageTemp, TypeClassTemp,
                              TypeTemp)

if TYPE_CHECKING:
    from pystatic.manager import Manager

ImpItem = Union[TypeModuleTemp, TypePackageTemp]


class Node:
    def __init__(self, content: 'ImpItem'):
        self.child: Dict[str, 'Node'] = {}
        self.content = content

    def march(self, name: str) -> Optional['Node']:
        return self.child.get(name)


def dot_before_imp(to_imp: str) -> int:
    i = 0
    while len(to_imp) > i and to_imp[i] == '.':
        i += 1
    return i


def uri2list(uri: str) -> List[str]:
    return [item for item in uri.split('.') if item != '']


def module_get_imp_uri(to_imp: str, cur_module: TypeModuleTemp) -> List[str]:
    i = dot_before_imp(to_imp)
    if i == 0:
        return uri2list(to_imp)
    else:
        cur_module_uri = cur_module.uri.split('.')[:-1]
        rel_uri = uri2list(to_imp[i:])

        if i == 1:
            return cur_module_uri + rel_uri
        else:
            return cur_module_uri[:-(i // 2)] + rel_uri


def package_get_imp_uri(to_imp: str,
                        cur_package: TypePackageTemp) -> List[str]:
    i = dot_before_imp(to_imp)
    package_uris = uri2list(cur_package.uri)
    if i == 0:
        return package_uris + uri2list(to_imp)
    else:
        rel_uri = uri2list(to_imp[i:])

        if i == 1:
            return package_uris + rel_uri
        else:
            return package_uris[:-(i // 2)] + rel_uri


class ModuleFinder:
    """PEP 561

    - Stubs or Python source manually put at the beginning of the path($MYPYPATH)
    - User code - files the type checker is running on.
    - Stub packages.
    - Inline packages.
    - Typeshed.
    """
    def __init__(self, manual_path: List[str], user_path: List[str],
                 sitepkg: List[str], typeshed: Optional[List[str]],
                 manager: 'Manager'):
        search_path = manual_path + user_path + sitepkg
        if typeshed:
            search_path += typeshed

        rt_pkg = TypePackageTemp(search_path, '', manager)
        self.manager = manager
        self.root = Node(rt_pkg)

    def _search_type_file(self, uri: List[str], paths: List[str],
                          start) -> List[str]:
        len_uri = len(uri)
        for i in range(start, len_uri):
            if not paths:
                return []
            ns_paths = []  # namespace packages
            target = None
            for path in paths:
                sub_target = os.path.normpath(os.path.join(path, uri[i]))

                if i == len_uri - 1:
                    pyi_file = sub_target + '.pyi'
                    py_file = sub_target + '.py'
                    if os.path.isfile(pyi_file):
                        return [pyi_file]
                    if os.path.isfile(py_file):
                        return [py_file]

                if os.path.isdir(sub_target):
                    init_file = os.path.join(sub_target, '__init__.py')
                    if os.path.isfile(init_file):
                        target = sub_target
                    else:
                        ns_paths.append(sub_target)

            if target:
                paths = [target]
            else:
                paths = ns_paths
        return paths

    def find_by_paths(self, paths: List[str], uri: List[str], start: int,
                      end: int) -> Optional[ImpItem]:
        def gen_impItem(paths: List[str]):
            isdir = False
            for path in paths:
                if not os.path.exists(path):
                    return None
                if os.path.isdir(path):
                    isdir = True
                elif isdir:
                    return None

            if isdir:  # package
                return TypePackageTemp(paths, '.'.join(uri[:end]),
                                       self.manager)
            else:
                assert len(paths) == 1  # module
                return self.manager.semanal_module(paths[0],
                                                   '.'.join(uri[:end]))

        paths = self._search_type_file(uri[start:end], paths, 0)
        if paths:
            return gen_impItem(paths)
        else:
            return None

    def search_imp(self, uris: List[str]) -> Tuple['ImpItem', int]:
        curnode = self.root
        for i, sub_uri in enumerate(uris):
            nextnode = curnode.march(sub_uri)
            if not nextnode:
                if isinstance(curnode.content, TypeModuleTemp):
                    return curnode.content, i
                else:
                    res = self.find_by_paths(curnode.content.path, uris, i,
                                             i + 1)
                    if res is None:
                        return curnode.content, i
                    else:
                        curnode.child[sub_uri] = Node(res)
                        curnode = curnode.child[sub_uri]
            else:
                curnode = nextnode
        return curnode.content, len(uris)

    def _find(self, uris: List[str]) -> Optional[TypeTemp]:
        res, i = self.search_imp(uris)
        if i == 0:
            return None
        elif i != len(uris) and isinstance(res, TypePackageTemp):
            return None
        else:
            for sub_name in uris[i:]:
                if isinstance(res, TypeClassTemp):
                    res = res.get_type(sub_name)
                else:
                    return None
            return res

    def find_from_module(self, to_imp: str,
                         cur_module: TypeModuleTemp) -> Optional[TypeTemp]:
        to_imp_uris = module_get_imp_uri(to_imp, cur_module)
        return self._find(to_imp_uris)

    def find_from_package(self, to_imp: str,
                          cur_package: TypePackageTemp) -> Optional[TypeTemp]:
        to_imp_uris = package_get_imp_uri(to_imp, cur_package)
        return self._find(to_imp_uris)
