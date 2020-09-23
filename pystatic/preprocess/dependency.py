from typing import List, Dict, Deque
from collections import deque
from pystatic.typesys import TypeClassTemp


class _Node:
    def __init__(self, clstemp: TypeClassTemp) -> None:
        self.clstemp = clstemp
        self.dependency: List['_Node'] = []

        self.indeg: int = 0

    def add_dependency(self, node: '_Node'):
        if node not in self.dependency:
            self.dependency.append(node)


class DependencyGraph:
    def __init__(self) -> None:
        self._nodes: List['_Node'] = []
        self._mapping: Dict[TypeClassTemp, _Node] = {}

    def lookup(self, temp: TypeClassTemp):
        if temp not in self._mapping:
            newnode = _Node(temp)
            self._nodes.append(newnode)
            self._mapping[temp] = newnode
        return self._mapping[temp]

    def add_dependency(self, temp_from: TypeClassTemp, temp_to: TypeClassTemp):
        from_node = self.lookup(temp_from)
        to_node = self.lookup(temp_to)
        from_node.add_dependency(to_node)

    def toposort(self) -> List['TypeClassTemp']:
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
            curnode = que[0]
            que.popleft()
            res.append(curnode.clstemp)
            for depend_node in curnode.dependency:
                depend_node.indeg -= 1
                if depend_node.indeg == 0:
                    que.append(depend_node)

        return list(reversed(res))
