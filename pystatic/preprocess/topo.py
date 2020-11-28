from typing import List, Dict, Deque, Set
from collections import deque
from pystatic.preprocess.prepinfo import PrepDef


class _Node:
    __slots__ = ['prepdef', 'dependency', 'indeg']

    def __init__(self, prepdef: 'PrepDef') -> None:
        self.prepdef = prepdef
        self.dependency: Set['_Node'] = set()

        self.indeg: int = 0

    def add_dependency(self, node: '_Node'):
        self.dependency.add(node)


class DependencyGraph:
    def __init__(self) -> None:
        self._nodes: List['_Node'] = []
        self._mapping: Dict['PrepDef', _Node] = {}

    def lookup(self, prepdef: 'PrepDef'):
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

    def toposort(self) -> List['PrepDef']:
        que: Deque['_Node'] = deque()
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
                raise NotImplementedError(
                    "resolve dependency error not implemented")

        return res
