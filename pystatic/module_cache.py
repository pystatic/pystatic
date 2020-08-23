import os
from pystatic.config import CheckMode
from typing import Optional, Dict, List, TYPE_CHECKING, Tuple
from pystatic.typesys import TypeClassTemp, TypeModuleTemp, TypePackageTemp, TypeTemp
from pystatic.module_finder import ModuleFinder

if TYPE_CHECKING:
    from pystatic.manager import Manager
    from pystatic.typesys import ImpItem


class Node:
    def __init__(self, content: 'ImpItem'):
        self.child: Dict[str, 'Node'] = {}
        self.content = content

    def march(self, name: str) -> Optional['Node']:
        return self.child.get(name)


class ModuleCache:
    def __init__(self, manager: 'Manager'):
        search_path = manager.config.manual_path
        search_path += [manager.config.cwd]  # TODO: support relative import
        search_path += manager.config.sitepkg
        # TODO: typeshed
        self.finder = ModuleFinder(manager)
        self.manager = manager
        rt_pkg = TypePackageTemp(search_path, '', manager)
        self.root = Node(rt_pkg)

    def lookup(self, uris: List[str]) -> Tuple['ImpItem', int]:
        curnode = self.root
        for i in range(len(uris)):
            nextnode = curnode.march(uris[i])
            if not nextnode:
                if isinstance(curnode.content, TypeModuleTemp):
                    return curnode.content, i
                else:
                    res = self.finder.find_pathes(curnode.content.path,
                                                  [uris[i]])
                    if res is None:
                        return curnode.content, i
                    else:
                        curnode.child[uris[i]] = Node(res)
                        curnode = curnode.child[uris[i]]
            else:
                curnode = nextnode
        return curnode.content, len(uris)

    def _dot_before_imp(self, to_imp: str) -> int:
        i = 0
        while len(to_imp) > i and to_imp[i] == '.':
            i += 1
        return i

    def _get_imp_uri(self, to_imp: str, cur_module: 'ImpItem') -> List[str]:
        i = self._dot_before_imp(to_imp)
        cur_module_uri = cur_module.exposed_pkg().split('.')
        if cur_module_uri[0] == '':
            cur_module_uri = []
        rel_uri = to_imp[i:].split('.')
        if i == 0:
            return cur_module_uri + rel_uri
        else:
            return cur_module_uri[:-(i // 2)] + rel_uri

    def lookup_from_module(self, to_imp: str,
                           cur_module: 'ImpItem') -> Optional[TypeTemp]:
        to_imp_uris = self._get_imp_uri(to_imp, cur_module)
        res, i = self.lookup(to_imp_uris)
        if i == 0:
            return None
        else:
            for sub_name in to_imp_uris[i:]:
                if isinstance(res, TypeClassTemp):
                    res = res.get_type(sub_name)
                else:
                    return None
            return res
