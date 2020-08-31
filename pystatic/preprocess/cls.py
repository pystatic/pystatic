import ast
from typing import Tuple, List, Set
from pystatic.env import Environment
from pystatic.typesys import TypeIns, TypeVar
from pystatic.util import ParseException
from pystatic.preprocess.annotation import (parse_ann_ast, SimpleTypeNode,
                                            SimpleTypeNodeTag, get_type,
                                            check_appliable)


def get_cls_typevars(node: ast.ClassDef,
                     env: Environment) -> Tuple[List[str], List[TypeIns]]:
    return ClassTypeVarGetter().get_cls_typevars(node, env)


class ClassTypeVarGetter:
    def __init__(self) -> None:
        self.met_gen = False

    def get_cls_typevars(self, node: ast.ClassDef,
                         env: Environment) -> Tuple[List[str], List[TypeIns]]:
        """Get TypeVar used in the class definition and return the list of base classes"""
        var_list: List[str] = []
        var_set: Set[str] = set()
        base_list: List[TypeIns] = []

        for base in node.bases:
            try:
                simple_tree = parse_ann_ast(base, False, None)

                self._get_cls_typevars(simple_tree, var_set, var_list, env)
                base_tp = get_type(simple_tree, env)
                if base_tp:
                    base_list.append(base_tp)
            except ParseException as e:
                msg = e.msg if e.msg else 'invalid base class'
                if e.msg:
                    env.add_err(e.node, msg)

        return var_list, base_list

    def _get_cls_typevars(self, s_node: 'SimpleTypeNode', var_set: Set[str],
                          var_list: List[str], env: Environment) -> None:
        """Get TypeVar used in an annotation represented by a simple tree"""
        def check_type(type_name: str):
            """If type_name is a TypeVar, then check and add it to the list.

            Return the type that type_name represents.
            """
            nonlocal var_set, var_list, env
            tp = env.lookup_type(type_name)
            if tp is None:
                raise ParseException(s_node.node, f'{type_name} is unbound')
            elif isinstance(tp, TypeVar):
                if type_name not in var_set:
                    if self.met_gen:
                        raise ParseException(s_node.node,
                                             f'{type_name} should in Generic')
                    else:
                        var_list.append(type_name)
                        var_set.add(type_name)
            return tp

        def meet_generic():
            """Meet Generic

            - All type variable should be included in the Generic.
            - There should be only one Generic.
            """
            nonlocal var_list, var_set, self
            if self.met_gen:
                raise ParseException(ast_node, 'only one Generic allowed')
            self.met_gen = True

            var_list.clear()
            gen_set = set()
            for sub_node in s_node.param:
                tp_var = env.lookup_type(sub_node.name)
                if not isinstance(tp_var, TypeVar):
                    raise ParseException(
                        ast_node, 'only typevar allowed inside Generic')
                else:
                    if sub_node.name in gen_set:
                        raise ParseException(
                            ast_node, f'duplicate typevar {sub_node.name}')
                    gen_set.add(sub_node.name)
                    var_list.append(sub_node.name)

            if len(var_set - gen_set) > 0:
                free_var = list(var_set - gen_set)
                raise ParseException(
                    ast_node, f'{", ".join(free_var)} should inside Generic')
            var_set = gen_set

        ast_node = s_node.node

        if s_node.tag == SimpleTypeNodeTag.ATTR:
            self._get_cls_typevars(s_node.left, var_set, var_list, env)
            check_type(s_node.name)
            return None
        elif s_node.tag == SimpleTypeNodeTag.NAME:
            check_type(s_node.name)
            return None
        elif s_node.tag == SimpleTypeNodeTag.SUBS:
            tp = check_type(s_node.name)
            self._get_cls_typevars(s_node.left, var_set, var_list, env)
            if s_node.name == 'Generic':
                meet_generic()
            else:
                for sub_node in s_node.param:
                    self._get_cls_typevars(sub_node, var_set, var_list, env)
                succeed, err_info = check_appliable(tp, len(s_node.param))
                if not succeed:
                    raise ParseException(ast_node, err_info)
        elif s_node.tag == SimpleTypeNodeTag.LIST:
            for sub_node in s_node.param:
                self._get_cls_typevars(sub_node, var_set, var_list, env)
            return None
        elif s_node.tag == SimpleTypeNodeTag.ELLIPSIS:
            pass
        else:
            raise ParseException(ast_node, 'invalid syntax')
