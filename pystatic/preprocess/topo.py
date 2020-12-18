from typing import Dict, Deque, Set
from collections import deque
from pystatic.preprocess.prepinfo import PrepDef
from pystatic.error.errorbox import ErrorBox
from pystatic.error.errorcode import *


class _Node:
    __slots__ = ["prepdef", "dependency", "indeg"]

    def __init__(self, prepdef: "PrepDef") -> None:
        self.prepdef = prepdef
        self.dependency: Set["_Node"] = set()
        self.indeg: int = 0

    def add_dependency(self, node: "_Node"):
        self.dependency.add(node)


def _resolve_loop(cur_node: _Node, added: set, nodelist: List[_Node], errbox: ErrorBox):
    added.add(cur_node)
    nodelist.append(cur_node)
    for next_node in cur_node.dependency:
        assert next_node.indeg != 0
        if next_node in added:
            loop_ref_list = []
            if next_node == cur_node:
                glob_symid = cur_node.prepdef.def_prepinfo.glob_symid
                cur_item = (glob_symid, cur_node.prepdef.defnode)
                loop_ref_list = [cur_item, cur_item]
            else:
                for i in range(len(nodelist) - 2, 0, -1):
                    glob_symid = nodelist[i].prepdef.def_prepinfo.glob_symid
                    loop_ref_list.append((glob_symid, nodelist[i].prepdef.defnode))
                    if nodelist[i] == next_node:
                        break
            errbox.add_err(ReferenceLoop(loop_ref_list))

        else:
            _resolve_loop(next_node, added, nodelist, errbox)
        next_node.indeg -= 1
    added.remove(cur_node)
    nodelist.pop()


def resolve_loop(cur_node: _Node, errbox: ErrorBox):
    added = set()
    nodelist = []
    _resolve_loop(cur_node, added, nodelist, errbox)


class DependencyGraph:
    def __init__(self, errbox: "ErrorBox") -> None:
        self._nodes: List["_Node"] = []
        self._mapping: Dict["PrepDef", _Node] = {}
        self.errbox = errbox

    def lookup(self, prepdef: "PrepDef"):
        if prepdef not in self._mapping:
            newnode = _Node(prepdef)
            self._nodes.append(newnode)
            self._mapping[prepdef] = newnode
        return self._mapping[prepdef]

    def add_dependency(self, def_from: PrepDef, def_to: PrepDef):
        from_node = self.lookup(def_from)
        to_node = self.lookup(def_to)
        to_node.add_dependency(from_node)

    def add_prepdef(self, prepdef: PrepDef):
        self.lookup(prepdef)

    def toposort(self) -> List["PrepDef"]:
        que: Deque["_Node"] = deque()
        for node in self._nodes:
            node.indeg = 0
        for node in self._nodes:
            for depend_node in node.dependency:
                depend_node.indeg += 1
        for node in self._nodes:
            if node.indeg == 0:
                que.append(node)

        res = []

        while len(que) != 0:
            curnode = que.popleft()
            res.append(curnode.prepdef)
            for depend_node in curnode.dependency:
                depend_node.indeg -= 1
                if depend_node.indeg == 0:
                    que.append(depend_node)

        for node in self._nodes:
            if node.indeg != 0:
                resolve_loop(node, self.errbox)

        return res
