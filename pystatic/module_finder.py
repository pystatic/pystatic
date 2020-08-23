import os
from typing import List, Optional, Union, TYPE_CHECKING
from pystatic.typesys import TypeModuleTemp, TypePackageTemp

if TYPE_CHECKING:
    from pystatic.manager import Manager

ImpItem = Union[TypeModuleTemp, TypePackageTemp]


class ModuleFinder:
    """PEP 561

    - Stubs or Python source manually put at the beginning of the path($MYPYPATH)
    - User code - files the type checker is running on.
    - Stub packages.
    - Inline packages.
    - Typeshed.
    """
    def __init__(self, manager: 'Manager'):
        self.manager = manager
        self.config = manager.config

    def _search_type_file(self, uri: List[str], pathes: List[str],
                          start) -> List[str]:
        len_uri = len(uri)
        for i in range(start, len_uri):
            if not pathes:
                return []
            ns_pathes = []  # namespace packages
            target = None
            for path in pathes:
                sub_target = os.path.join(path, uri[i])

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
                        ns_pathes.append(sub_target)

            if target:
                pathes = [target]
            else:
                pathes = ns_pathes
        return pathes

    def find_pathes(self, pathes: List[str],
                    uri: List[str]) -> Optional[ImpItem]:
        def gen_impItem(pathes: List[str]):
            isdir = False
            for path in pathes:
                if not os.path.exists(path):
                    return None
                if os.path.isdir(path):
                    isdir = True
                elif isdir:
                    return None

            if isdir:  # package
                return TypePackageTemp(pathes, '.'.join(uri), self.manager)
            else:
                assert len(pathes) == 1  # module
                return self.manager.semanal_module(pathes[0], '.'.join(uri))

        pathes = self._search_type_file(uri, pathes, 0)
        if pathes:
            return gen_impItem(pathes)
        else:
            return None
