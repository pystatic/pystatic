import ast
import copy
from typing import Optional, Dict, List
from pystatic.typesys import (TypeType, TypeVar, ellipsis_type, none_type)
from pystatic.env import Environment
from pystatic.visitor import BaseVisitor
from pystatic.util import BindException, ParseException


def parse_annotation(node: ast.AST, env: Environment,
                     def_check: bool) -> Optional[TypeType]:
    """Get the type according to the annotation

    If def_check is True, then it will make sure that the annotation not
    surrounded by quotes must be defined earlier.
    """
    try:
        return AnnotationEval(env, def_check, False, None).accept(node)
    except (SyntaxError, ParseException):
        return None


def parse_comment_annotation(node: ast.AST,
                             env: Environment) -> Optional[TypeType]:
    """Get the type according to the type comment"""
    comment = node.type_comment if node.type_comment else None
    if not comment:
        return None
    try:
        str_node = ast.parse(
            comment,
            mode='eval')  # for annotations that's str we first parse it
    except SyntaxError:
        return None
    else:
        if isinstance(str_node, ast.Expression):
            try:
                return AnnotationEval(env, False, True, node).accept(str_node)
            except (SyntaxError, ParseException):
                return None
        else:
            # TODO: add error?
            return None


def get_typevar_from_ann(node: ast.AST, env: Environment,
                         collect: Dict[str, TypeVar]):
    TypeVarCollector(env, collect).accept(node)


class TypeVarCollector(BaseVisitor):
    def __init__(self, env: 'Environment', collect: Dict[str, TypeVar]):
        super().__init__()
        self.env = env
        self.collect = collect

    def visit_Name(self, node: ast.Name):
        tp = self.env.lookup_type(node.id)
        if isinstance(tp, TypeVar) and tp.name not in self.collect:
            self.collect[tp.name] = copy.deepcopy(tp)


# TODO: should replace this with EvalType(which should be more general)
class AnnotationEval(BaseVisitor):
    def __init__(self, env: 'Environment', def_check: bool, is_cons: bool,
                 cons_node: Optional[ast.AST]):
        super().__init__()
        self.env = env
        self.def_check = def_check
        self.is_cons = is_cons  # is this tree is parsed from a string annotation
        self.cons_node = cons_node  # the original node

        if self.is_cons:
            assert self.cons_node
            assert not self.def_check

    def get_realnode(self, node: ast.AST) -> ast.AST:
        """Get the right node to report errors.

        If current node is parsed as a string annotation, then return the original
        node, otherwise return the current node
        """
        if self.is_cons:
            assert self.cons_node
            return self.cons_node
        else:
            return node

    def visit_Attribute(self, node: ast.Attribute) -> Optional[TypeType]:
        left_type = self.visit(node.value)
        real_node = self.get_realnode(node)
        if left_type:
            assert isinstance(left_type, TypeType)
            cur_type = left_type.getattr(node.attr)
            if not isinstance(cur_type, TypeType):
                # TODO: reimplement this error information, B.C should show
                # B.C rather than C
                self.env.add_err(real_node, f'{node.attr} is not a type')
                return None
            return cur_type
        return None

    def visit_Constant(self, node: ast.Constant) -> Optional[TypeType]:
        if node.value is Ellipsis:
            return ellipsis_type
        elif node.value is None:
            return none_type
        else:
            try:
                tree_node = ast.parse(node.value, mode='eval')
                return AnnotationEval(self.env, False, True,
                                      node).accept(tree_node)
            except SyntaxError:
                real_node = self.get_realnode(node)
                assert real_node
                raise ParseException(real_node, f'invalid syntax')

    def visit_Name(self, node: ast.Name) -> Optional[TypeType]:
        real_node = self.get_realnode(node)

        tp_temp = self.env.lookup_type(node.id)
        if not tp_temp:
            self.env.add_err(real_node, f'{node.id} is not a type')
            return None
        else:
            tp_type = tp_temp.get_default_type()

        if self.def_check:
            assert not self.is_cons
            if not self.env.lookup_var(tp_type.basename):
                self.env.add_err(real_node, f'{node.id} undefined')
        return tp_type

    def visit_Subscript(self, node: ast.Subscript) -> Optional[TypeType]:
        value_tp = self.visit(node.value)
        if isinstance(value_tp, TypeType) and isinstance(
                node.slice, ast.Index):
            script_tp = self.visit(node.slice)
            if script_tp:
                assert isinstance(script_tp, tuple) or isinstance(
                    script_tp, TypeType) or isinstance(script_tp, list)

                bindlist: List[TypeType]
                if isinstance(script_tp, TypeType):
                    bindlist = [script_tp]
                else:
                    bindlist = list(script_tp)

                # give additional hints to type checker
                assert isinstance(value_tp, TypeType)
                try:
                    return value_tp.getitem(bindlist)
                except BindException as e:
                    # when binding fails, then bind all params to Any

                    # give additional hints to type checker
                    if isinstance(node.slice.value, ast.Tuple):
                        slot_list = node.slice.value.elts
                    elif isinstance(node.slice.value, ast.List):
                        slot_list = node.slice.value.elts
                    else:
                        slot_list = [node.slice.value]

                    if e.errors:
                        for pos, msg in e.errors:
                            if pos >= len(slot_list):
                                break
                            self.env.add_err(slot_list[pos], msg
                                             or 'bind error')

                        return value_tp.getitem([])
                    else:
                        self.env.add_err(node, e.msg or 'bind error')
                        return value_tp.getitem([])
        else:
            assert 0, "not implemented yet"
        return None

    def visit_Tuple(self, node: ast.Tuple):
        tp_list = []
        for subnode in node.elts:
            res = self.visit(subnode)
            if res:
                tp_list.append(res)
        return tuple(tp_list)

    def visit_List(self, node: ast.List):
        tp_list = []
        for subnode in node.elts:
            res = self.visit(subnode)
            if res:
                tp_list.append(res)
        return tp_list

    def visit_Index(self, node: ast.Index):
        return self.visit(node.value)

    def accept(self, node: ast.AST) -> Optional[TypeType]:
        return self.visit(node)
