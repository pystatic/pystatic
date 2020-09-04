import ast
from typing import Optional, List
from pystatic.env import Environment
from pystatic.arg import Argument, Arg
from pystatic.preprocess.annotation import parse_annotation
from pystatic.typesys import TypeFunc, any_type


def parse_arg(node: ast.arg, tp_scope: Environment):
    """Generate an Arg instance according to an ast.arg node"""
    new_arg = Arg(node.arg)
    if node.annotation:
        ann = parse_annotation(node.annotation, tp_scope, False)
        if not ann:
            return None
        else:
            new_arg.ann = ann
    return new_arg


def parse_arguments(node: ast.arguments,
                    tp_scope: Environment) -> Optional[Argument]:
    """Gernerate an Argument instance according to an ast.arguments node"""
    new_args = Argument()
    # order_arg: [**posonlyargs, **args]
    # order_kwarg: [**kwonlyargs]
    # these two lists are created to deal with default values
    order_arg: List[Arg] = []
    order_kwarg: List[Arg] = []
    ok = True

    # parse a list of args
    def add_to_list(target_list, order_list, args):
        global ok
        for arg in args:
            gen_arg = parse_arg(arg, tp_scope)
            if gen_arg:
                target_list.append(gen_arg)
                order_list.append(gen_arg)
            else:
                ok = False

    add_to_list(new_args.posonlyargs, order_arg, node.posonlyargs)
    add_to_list(new_args.args, order_arg, node.args)
    add_to_list(new_args.kwonlyargs, order_kwarg, node.kwonlyargs)

    # *args exists
    if node.vararg:
        result = parse_arg(node.vararg, tp_scope)
        if result:
            new_args.vararg = result
        else:
            ok = False

    # **kwargs exists
    if node.kwarg:
        result = parse_arg(node.kwarg, tp_scope)
        if result:
            new_args.kwarg = result
        else:
            ok = False

    for arg, value in zip(reversed(order_arg), reversed(node.defaults)):
        arg.valid = True
        arg.default = value  # TODO: add type check here

    for arg, value in zip(reversed(order_kwarg), reversed(node.kw_defaults)):
        arg.valid = True
        arg.default = value  # TODO: add type check here(here value is a node represent an expression)

    if ok:
        return new_args
    else:
        return None


def parse_func(node: ast.FunctionDef, env: Environment) -> Optional[TypeFunc]:
    """Get a function's type according to a ast.FunctionDef node"""
    argument = parse_arguments(node.args, env)
    if not argument:
        return None
    ret_type = None
    if node.returns:
        ret_type = parse_annotation(node.returns, env, False)
    if not ret_type:
        ret_type = any_type  # default return type is Any
    return TypeFunc(argument, ret_type)
