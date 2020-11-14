from typing import List, Dict, Deque
from collections import deque
from pystatic.typesys import TypeClassTemp
from pystatic.preprocess.prepinfo import prep_clsdef


class _Node:
    def __init__(self, clstemp: 'prep_clsdef') -> None:
        self.clstemp = clstemp
        self.dependency: List['_Node'] = []

        self.indeg: int = 0

    def add_dependency(self, node: '_Node'):
        if node not in self.dependency:
            self.dependency.append(node)


class DependencyGraph:
    def __init__(self) -> None:
        self._nodes: List['_Node'] = []
        self._mapping: Dict[prep_clsdef, _Node] = {}

    def lookup(self, clsdef: 'prep_clsdef'):
        if clsdef not in self._mapping:
            newnode = _Node(clsdef)
            self._nodes.append(newnode)
            self._mapping[clsdef] = newnode
        return self._mapping[clsdef]

    def add_dependency(self, cls_from: prep_clsdef, cls_to: prep_clsdef):
        from_node = self.lookup(cls_from)
        to_node = self.lookup(cls_to)
        from_node.add_dependency(to_node)

    def add_clsdef(self, clsdef: prep_clsdef):
        self.lookup(clsdef)

    def toposort(self) -> List['prep_clsdef']:
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
