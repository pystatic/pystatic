from collections import deque
from typing import Deque, List
from pystatic.visitor import NoGenVisitor, VisitorMethodNotFound
from pystatic.preprocess.topo import DependencyGraph
from pystatic.error.errorbox import ErrorBox
from pystatic.preprocess.prepinfo import *


def toposort_prepdef(prepinfo_list: List[PrepInfo], errbox: ErrorBox):
    graph = DependencyGraph(errbox)
    for prepinfo in prepinfo_list:
        _first_prepdef_visitor.set_prepinfo(prepinfo)
        for cls in prepinfo.cls.values():
            create_cls_dependency(graph, cls)
        for func in prepinfo.func.values():
            create_func_dependency(graph, func)
        for local in prepinfo.local.values():
            create_local_dependency(graph, local)

        if isinstance(prepinfo, PrepMethodInfo):
            for attr in prepinfo.var_attr.values():
                create_local_dependency(graph, attr)

    _first_prepdef_visitor.clear_prepinfo()
    return graph.toposort()


def create_cls_dependency(graph: "DependencyGraph", cls: prep_cls):
    queue: Deque["prep_cls"] = deque()
    queue.append(cls)

    while len(queue):
        curcls = queue.popleft()
        prepinfo = curcls.prepinfo
        graph.add_prepdef(curcls)
        node = cls.defnode
        assert isinstance(node, ast.ClassDef)

        for basenode in node.bases:
            inh_prepdef = _first_prepdef_visitor.accept(basenode)
            if inh_prepdef:
                graph.add_dependency(curcls, inh_prepdef)

        # FIXME: there should be dependency from this class to its attributes,
        # but doing so will create dependency loop.
        for func in prepinfo.func.values():
            create_func_dependency(graph, func)
        for local in prepinfo.local.values():
            create_local_dependency(graph, local)

        for subclsdef in prepinfo.cls.values():
            graph.add_dependency(curcls, subclsdef)
            queue.append(subclsdef)


def create_func_dependency(graph: "DependencyGraph", func: prep_func):
    node_list = func.defnodes
    graph.add_prepdef(func)
    for node in node_list:
        assert isinstance(node, ast.FunctionDef)
        arg_def = _first_prepdef_visitor.accept(node.args)
        if arg_def:
            graph.add_dependency(func, arg_def)
        ret_def = _first_prepdef_visitor.accept(node.returns)
        if ret_def:
            graph.add_dependency(func, ret_def)


def create_local_dependency(graph: "DependencyGraph", local: prep_local):
    node = local.defnode
    assert isinstance(node, (ast.Assign, ast.AnnAssign))
    graph.add_prepdef(local)
    if isinstance(node, ast.AnnAssign):
        depend = _first_prepdef_visitor.accept(node.annotation)
    else:
        depend = _first_prepdef_visitor.accept(node.value)
    if depend:
        graph.add_dependency(local, depend)


class _FirstPrepDefVisitor(NoGenVisitor):
    """Get the first class template.

    Used to build dependency graph. For example class C inherits A.B,
    this should return A's template so you can add edge from C to A.

    If the inherited class has already defined in symtable, then it won't
    return the TypeTemp of that class.
    """

    def __init__(self, prepinfo: Optional["PrepInfo"]) -> None:
        self.prepinfo = prepinfo

    def set_prepinfo(self, prepinfo: "PrepInfo"):
        self.prepinfo = prepinfo

    def clear_prepinfo(self):
        self.prepinfo = None

    def accept(self, node):
        assert self.prepinfo
        if not node:
            return None
        try:
            return self.visit(node)
        except VisitorMethodNotFound:
            return None

    def visit_Name(self, node: ast.Name):
        assert self.prepinfo
        prep_def = self.prepinfo.get_prep_def(node.id)
        return prep_def

    def visit_Attribute(self, node: ast.Attribute):
        return self.visit(node.value)

    def visit_Subscript(self, node: ast.Subscript):
        return self.visit(node.value)


_first_prepdef_visitor = _FirstPrepDefVisitor(None)
