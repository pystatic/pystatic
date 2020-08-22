import ast
import enum
from .typesys import TypeClass
from .env import Environment
from .visitor import ParseException


class TypeNodeTag(enum.Enum):
    ATTR = 0
    NAME = 1
    SUBS = 2
    LIST = 4
    ELLIPSIS = 5


class TypeNode(object):
    def __init__(self):
        self.name = ''
        self.node = None
        self.is_cons = False
        self.tag = TypeNodeTag.NAME
        self.param = []
        self.left: TypeNode
        self.attr: str


def typenode_parse_type(node, is_cons: bool, cons_node):
    new_node = TypeNode()
    if isinstance(node, ast.Constant):
        try:
            if node.value is Ellipsis:
                new_node.tag = TypeNodeTag.ELLIPSIS
                new_node.name = '...'
                return new_node
            elif node.value is None:
                new_node.tag = TypeNodeTag.NAME
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
        new_node.tag = TypeNodeTag.ATTR
        new_node.left = typenode_parse_type(node.value, is_cons, cons_node)
        new_node.attr = str(node.attr)
        new_node.name = new_node.left.name + '.' + new_node.attr
        return new_node
    elif isinstance(node, ast.Name):
        new_node.tag = TypeNodeTag.NAME
        new_node.name = node.id
        return new_node
    elif isinstance(node, ast.Subscript):
        new_node.tag = TypeNodeTag.SUBS
        new_node.left = typenode_parse_type(node.value, is_cons, cons_node)
        new_node.name = new_node.left.name
        if isinstance(node.slice, ast.Index):
            new_node.param = []
            if isinstance(node.slice.value, ast.Tuple):
                for sub_node in node.slice.value.elts:
                    new_node.param.append(
                        _typenode_parse_ptype(sub_node, is_cons, cons_node))
            else:
                new_node.param = [
                    _typenode_parse_ptype(node.slice.value, is_cons, cons_node)
                ]
        else:
            raise ParseException(node, 'invalid syntax')
        return new_node
    else:
        src_node = node if not is_cons else cons_node
        raise ParseException(src_node, '')


def _typenode_parse_ptype(node, is_cons, cons_node):
    if isinstance(node, ast.List):
        new_node = TypeNode()
        new_node.is_cons = is_cons
        new_node.tag = TypeNodeTag.LIST
        new_node.param = []
        new_node.node = node
        for sub_node in node.elts:
            new_node.param.append(
                typenode_parse_type(sub_node, is_cons, cons_node))
        return new_node
    else:
        return typenode_parse_type(node, is_cons, cons_node)


def get_type(node, env: Environment):
    if node.tag == TypeNodeTag.NAME:
        tp = env.lookup_type(node.name)
        if tp is None:
            raise ParseException(node.node, f'{node.name} unbound')
        else:
            return tp.instantiate([])
    elif node.tag == TypeNodeTag.ATTR:
        left_tp = get_type(node.left, env)
        if isinstance(left_tp, TypeClass):
            tp = left_tp.template.get_type(node.attr)  # type: ignore
            if tp is None:
                raise ParseException(
                    node.node, f'{left_tp.name} has no attribute {node.attr}')
            return tp.instantiate([])
        else:
            raise ParseException(
                node.node, f'{left_tp.name} has no attribute {node.attr}')
    elif node.tag == TypeNodeTag.SUBS:
        tp = get_type(node.left, env)
        param_list = []
        for param in node.param:
            p_tp = get_type(param, env)
            param_list.append(p_tp)
        return tp.template.instantiate(param_list)
    elif node.tag == TypeNodeTag.LIST:
        raise ParseException(node.node, 'not implemented yet')
    elif node.tag == TypeNodeTag.ELLIPSIS:
        raise ParseException(node.node, 'not implemented yet')
