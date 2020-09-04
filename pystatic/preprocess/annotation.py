import ast
import copy
from typing import Optional, Tuple, Dict
from pystatic.typesys import (TypeIns, ARIBITRARY_ARITY, TypeType, TypeVar,
                              ellipsis_type, none_type)
from pystatic.env import Environment
from pystatic.util import ParseException, BaseVisitor


def parse_annotation(node: ast.AST, env: Environment,
                     def_check: bool) -> Optional[TypeIns]:
    """Get the type according to the annotation
    
    If def_check is True, then it will make sure that the annotation not
    surrounded by quotes must be defined earlier.
    """
    tp_res = AnnotationEval(env, def_check, False, None).accept(node)
    if tp_res:
        return tp_res.instantiate()
    else:
        return None


def parse_comment_annotation(node: ast.AST,
                             env: Environment) -> Optional[TypeIns]:
    """Get the type according to the type comment"""
    comment = node.type_comment if node.type_comment else None
    if not comment:
        return None
    try:
        str_node = ast.parse(
            comment,
            mode='eval')  # for annotations that's str we first parse it
        if isinstance(str_node, ast.Expression):
            tp_res = AnnotationEval(env, False, True, node).accept(str_node)
            if tp_res:
                return tp_res.instantiate()
            else:
                return None
        else:
            raise ParseException(node, '')
    except (SyntaxError, ParseException):
        env.add_err(node, 'broken type comment')
        return None


def check_appliable(tp, param_cnt: int) -> Tuple[bool, str]:
    """Check whether the number of parameters match the type's definition
    If list is empty then we still consider it a valid match because the
    default is all Any. For special types like Optional, you must give at
    least one type parameter.

    Return (True, '') if it's appliable, otherwise return (None, <error_info>)
    """
    if tp.name == 'Optional':  # special judge
        assert tp.arity == 1
        if param_cnt != tp.arity:
            return False, f'Optional require {tp.arity} parameters'
        return True, ''

    if tp.arity == ARIBITRARY_ARITY:
        if param_cnt <= 0:
            return False, f'{tp.name} require at least one type parameter'
        else:
            return True, ''
    elif tp.arity == param_cnt or param_cnt == 0:
        return True, ''
    else:
        return False, f'{tp.name} require {tp.arity} but {param_cnt} given'


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


class AnnotationEval(BaseVisitor):
    def __init__(self, env: 'Environment', def_check: bool, is_cons: bool,
                 cons_node: Optional[ast.AST]):
        super().__init__()
        self.env = env
        self.def_check = def_check
        self.is_cons = is_cons
        self.cons_node = cons_node

        if self.is_cons:
            assert self.cons_node
            assert not self.def_check

    def visit_Attribute(self, node: ast.Attribute) -> Optional[TypeType]:
        left_tp = self.visit(node.value)
        if left_tp:
            return left_tp.getattr(node.attr)
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
                real_node = self.cons_node if self.is_cons else node
                assert real_node
                raise ParseException(real_node, f'invalid syntax')

    def visit_Name(self, node: ast.Name) -> Optional[TypeType]:
        real_node = self.cons_node if self.is_cons else node
        assert real_node
        tp_temp = self.env.lookup_type(node.id)
        if not tp_temp:
            self.env.add_err(real_node, f'{node.id} undefined')
            return None
        else:
            tp = tp_temp.get_type()

        if not tp:
            self.env.add_err(real_node, f'{node.id} undefined')
            return None
        elif not isinstance(tp, TypeType):
            self.env.add_err(real_node, f'{node.id} is not a type')
            return None
        else:
            if self.def_check:
                assert not self.is_cons
                if not self.env.lookup_var(tp.basename):
                    self.env.add_err(real_node, f'{node.id} undefined')
            return tp

    def visit_Subscript(self, node: ast.Subscript) -> Optional[TypeType]:
        assert 0, "generic currently is not supported"
        value_tp = self.visit(node.value)
        if isinstance(value_tp, TypeType):
            if isinstance(node.slice, ast.Index):
                index_tp = self.visit(node.slice)
                if index_tp:
                    return value_tp.getitem(index_tp)
        return None

    def visit_Tuple(self, node: ast.Tuple):
        tp_list = []
        for subnode in node.elts:
            res = self.visit(subnode)
            if res is None:
                self.env.add_err(subnode, f'type undefined')
            else:
                tp_list.append(res)
        return tuple(tp_list)

    def visit_List(self, node: ast.List):
        tp_list = []
        for subnode in node.elts:
            res = self.visit(subnode)
            if res is None:
                self.env.add_err(subnode, f'type undefined')
            else:
                tp_list.append(res)
        return tp_list

    def visit_Index(self, node: ast.Index):
        return self.visit(node.value)

    def accept(self, node: ast.AST) -> Optional[TypeType]:
        return self.visit(node)
