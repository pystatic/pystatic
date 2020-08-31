import ast
import enum
from typing import Optional, List, Union, Tuple
from pystatic.typesys import (TypeClass, TypeIns, TypeTemp, ARIBITRARY_ARITY)
from pystatic.env import Environment
from pystatic.util import ParseException


def parse_annotation(node: ast.AST, env: Environment) -> Optional[TypeIns]:
    """Get the type according to the annotation"""
    return AnnotationParser(env).accept(node)


def parse_comment_annotation(node: ast.AST,
                             env: Environment) -> Optional[TypeIns]:
    """Get the type according to the type comment"""
    comment = node.type_comment if node.type_comment else None
    if not comment:
        return None
    try:
        node = ast.parse(
            comment,
            mode='eval')  # for annotations that's str we first parse it
        if isinstance(node, ast.Expression):
            return AnnotationParser(env).accept(node.body)
        else:
            raise ParseException(node, '')
    except (SyntaxError, ParseException):
        env.add_err(node, 'broken type comment')
        return None


class AnnotationParser(object):
    """Parse annotations"""
    def __init__(self, env: Environment):
        self.env = env

    def accept(self, node: ast.AST) -> Optional[TypeIns]:
        """Return the type this node represents"""
        try:
            new_tree = parse_ann_ast(node, False, None)
            return get_type(new_tree, self.env)
        except ParseException as e:
            self.env.add_err(e.node, e.msg)
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


# Parse annotation nodes
# first convert ast to a simpler tree structure and then analyse this tree
class SimpleTypeNodeTag(enum.Enum):
    ATTR = 0
    NAME = 1
    SUBS = 2
    LIST = 4
    ELLIPSIS = 5


class SimpleTypeNode(object):
    def __init__(self,
                 node: ast.AST,
                 name: str,
                 is_cons: bool = False,
                 tag: SimpleTypeNodeTag = SimpleTypeNodeTag.NAME):
        self.node = node
        self.name = name
        self.is_cons = is_cons
        self.tag = tag
        self.param: List[SimpleTypeNode] = []
        self.left: SimpleTypeNode
        self.attr: str


def parse_ann_ast(node, is_cons: bool, cons_node) -> SimpleTypeNode:
    """Parse an annotation ast to a simpler tree.

    If it fails, throw ParseException.
    """
    new_node = SimpleTypeNode(node, '', is_cons)
    if isinstance(node, ast.Constant):
        try:
            if node.value is Ellipsis:
                new_node.tag = SimpleTypeNodeTag.ELLIPSIS
                new_node.name = '...'
                return new_node
            elif node.value is None:
                new_node.tag = SimpleTypeNodeTag.NAME
                new_node.name = 'None'
                return new_node
            elif not isinstance(node.value, str):
                raise ParseException(node, 'invalid syntax')
            parsed_node = ast.parse(node.value, mode='eval')
            if isinstance(parsed_node, ast.Expression):
                if not is_cons:
                    is_cons = True
                    cons_node = node
                node = parsed_node.body
            else:
                raise ParseException(node, 'invalid syntax')
        except SyntaxError:
            raise ParseException(node, 'invalid syntax')

    new_node.node = node
    new_node.is_cons = is_cons
    if isinstance(node, ast.Attribute):
        new_node.tag = SimpleTypeNodeTag.ATTR
        new_node.left = parse_ann_ast(node.value, is_cons, cons_node)
        new_node.attr = str(node.attr)
        new_node.name = new_node.left.name + '.' + new_node.attr
        return new_node
    elif isinstance(node, ast.Name):
        new_node.tag = SimpleTypeNodeTag.NAME
        new_node.name = node.id
        return new_node
    elif isinstance(node, ast.Subscript):
        new_node.tag = SimpleTypeNodeTag.SUBS
        new_node.left = parse_ann_ast(node.value, is_cons, cons_node)
        new_node.name = new_node.left.name
        if isinstance(node.slice, ast.Index):
            new_node.param = []
            if isinstance(node.slice.value, ast.Tuple):
                for sub_node in node.slice.value.elts:
                    new_node.param.append(
                        _parse_ann_ast_allow_list(sub_node, is_cons,
                                                  cons_node))
            else:
                new_node.param = [
                    _parse_ann_ast_allow_list(node.slice.value, is_cons,
                                              cons_node)
                ]
        else:
            raise ParseException(node, 'invalid syntax')
        return new_node
    else:
        src_node = node if not is_cons else cons_node
        raise ParseException(src_node, '')


def _parse_ann_ast_allow_list(node, is_cons, cons_node) -> SimpleTypeNode:
    """allow list node as root"""
    if isinstance(node, ast.List):
        new_node = SimpleTypeNode(node,
                                  'list',
                                  is_cons=is_cons,
                                  tag=SimpleTypeNodeTag.LIST)
        for sub_node in node.elts:
            new_node.param.append(parse_ann_ast(sub_node, is_cons, cons_node))
        return new_node
    else:
        return parse_ann_ast(node, is_cons, cons_node)


def get_type(node: SimpleTypeNode, env: Environment) -> Optional[TypeIns]:
    """From a simple tree node to the type it represents"""
    tp: Union[TypeTemp, TypeIns, None]
    if node.tag == SimpleTypeNodeTag.NAME:
        tp = env.lookup_type(node.name)
        if tp is None:
            raise ParseException(node.node, f'{node.name} unbound')
        else:
            return tp.instantiate([])
    elif node.tag == SimpleTypeNodeTag.ATTR:
        left_tp = get_type(node.left, env)
        if not left_tp:
            return None
        if isinstance(left_tp, TypeClass):
            tp = left_tp.template.get_type(node.attr)  # type: ignore
            if tp is None:
                raise ParseException(
                    node.node, f'{left_tp.name} has no attribute {node.attr}')
            return tp.instantiate([])  # type: ignore
        else:
            raise ParseException(
                node.node, f'{left_tp.name} has no attribute {node.attr}')
    elif node.tag == SimpleTypeNodeTag.SUBS:
        tp = get_type(node.left, env)
        if not tp:
            return None
        param_list = []
        for param in node.param:
            p_tp = get_type(param, env)
            param_list.append(p_tp)
        return tp.template.instantiate(param_list)
    elif node.tag == SimpleTypeNodeTag.LIST:
        raise ParseException(node.node, 'not implemented yet')
    elif node.tag == SimpleTypeNodeTag.ELLIPSIS:
        raise ParseException(node.node, 'not implemented yet')
    return None
