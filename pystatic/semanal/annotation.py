import ast
import enum
from typing import Optional, List, Tuple, Union, Set
from pystatic.typesys import (TypeClass, TypeIns, TypeTemp, TypeVar,
                              ARIBITRARY_ARITY)
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


def get_cls_type_params(node: ast.ClassDef,
                        env: Environment) -> Tuple[List[str], List[TypeIns]]:
    var_list: List[str] = []
    var_set: Set[str] = set()
    base_list: List[TypeIns] = []
    for base in node.bases:
        try:
            new_tree = parse_ann_ast(base, False, None)
            _get_cls_type_params(new_tree, var_set, var_list, env, False)
            base_tp = get_type(new_tree, env)
            if base_tp:
                base_list.append(base_tp)
        except ParseException as e:
            msg = e.msg if e.msg else 'invalid base class'
            if e.msg:
                env.add_err(e.node, msg)
    return var_list, base_list


def _get_cls_type_params(node, var_set: Set[str], var_list: List[str],
                         env: Environment, met_gen: bool) -> None:
    def check_type(type_name: str):
        """If type_name is a TypeVar, then check and add it to the list

        Return the type type_name represents.
        """
        nonlocal var_set, var_list, env, met_gen
        tp = env.lookup_type(type_name)
        if tp is None:
            raise ParseException(node.node, f'{type_name} is unbound')
        elif isinstance(tp, TypeVar):
            if type_name not in var_set:
                if met_gen:
                    raise ParseException(node.node,
                                         'all typevar should in Generic')
                else:
                    var_list.append(type_name)
                    var_set.add(type_name)
        return tp

    def meet_generic():
        """Meet Generic
        
        - All type variable should be included in the Generic.
        - There should only be one Generic
        """
        nonlocal met_gen, var_list, var_set
        if met_gen:
            raise ParseException(ast_node, 'only one Generic allowed')
        met_gen = True

        var_list.clear()
        gen_set = set()
        for sub_node in node.param:
            tp_var = env.lookup_type(sub_node.name)
            if not isinstance(tp_var, TypeVar):
                raise ParseException(ast_node,
                                     'only typevar allowed inside Generic')
            else:
                if sub_node.name in gen_set:
                    raise ParseException(ast_node,
                                         f'duplicate typevar {sub_node.name}')
                gen_set.add(sub_node.name)
                var_list.append(sub_node.name)

        if len(var_set - gen_set) > 0:
            free_var = list(var_set - gen_set)
            raise ParseException(
                ast_node, f'{", ".join(free_var)} should inside Generic')
        var_set = gen_set

    ast_node = node.node

    if node.tag == SimpleTypeNodeTag.ATTR:
        _get_cls_type_params(node.left, var_set, var_list, env, met_gen)
        check_type(node.name)
        return None
    elif node.tag == SimpleTypeNodeTag.NAME:
        check_type(node.name)
        return None
    elif node.tag == SimpleTypeNodeTag.SUBS:
        tp = check_type(node.name)
        _get_cls_type_params(node.left, var_set, var_list, env, met_gen)
        if node.name == 'Generic':
            meet_generic()
        else:
            for sub_node in node.param:
                _get_cls_type_params(sub_node, var_set, var_list, env, met_gen)
            check_appliable(node, tp, len(node.param))
    elif node.tag == SimpleTypeNodeTag.LIST:
        for sub_node in node.param:
            _get_cls_type_params(sub_node, var_set, var_list, env, met_gen)
        return None
    elif node.tag == SimpleTypeNodeTag.ELLIPSIS:
        pass
    else:
        raise ParseException(ast_node, 'invalid syntax')


def check_appliable(node, tp, param_cnt: int):
    """Check whether the number of parameters match the type's definition
    If list is empty then we still consider it a valid match because the
    default is all Any.

    However, for Optional, you must specify a type.
    """
    if tp.name == 'Optional':  # special judge
        assert tp.arity == 1
        if param_cnt != tp.arity:
            raise ParseException(node,
                                 f'Optional require {tp.arity} parameter')
        return True

    if tp.arity == ARIBITRARY_ARITY:
        if param_cnt <= 0:
            raise ParseException(
                node, f'{tp.name} require at least one type parameter')
        else:
            return True
    elif tp.arity == param_cnt or param_cnt == 0:
        return True
    else:
        raise ParseException(
            node, f'{tp.name} require {tp.arity} but {param_cnt} given')


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
    """Parse an annotation ast to a simpler tree"""
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
