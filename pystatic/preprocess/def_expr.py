import ast
from pystatic.symtable import SymTable, TableScope, TypeDefNode
from typing import Callable, List, Optional, Union
from pystatic.typesys import TypeIns, TypeType, any_ins
from pystatic.predefined import TypeFuncIns
from pystatic.arg import Argument, Arg
from pystatic.option import Option
from pystatic.exprparse import eval_expr
from pystatic.message import MessageBox
from pystatic.preprocess.prepinfo import *


def eval_typedef_expr(node: TypeDefNode, prepinfo: PrepInfo,
                      annotation: bool) -> Option[TypeIns]:
    if isinstance(node, str):
        res_option = eval_str_type(node, prepinfo)
    elif isinstance(node, ast.Assign) or isinstance(node, ast.AnnAssign):
        res_option = eval_assign_type(node, prepinfo)
    elif isinstance(node, ast.FunctionDef):
        raise NotImplementedError()
    else:
        res_option = eval_expr(node, prepinfo, annotation=True)
    if annotation:
        res_type = res_option.value
        if isinstance(res_type, TypeType):
            tpins = res_type.getins(res_option)
            res_option.value = tpins
    return res_option


def eval_str_type(s: str, prepinfo: PrepInfo) -> Option[TypeIns]:
    try:
        treenode = ast.parse(s, mode='eval')
        if hasattr(treenode, 'body'):
            return eval_expr(treenode.body, prepinfo)  # type: ignore
        else:
            res_option = Option(any_ins)
            # TODO: add error here
            return res_option
    except SyntaxError:
        res_option = Option(any_ins)
        # TODO: add error here
        return res_option


def eval_assign_type(node: Union[ast.Assign, ast.AnnAssign],
                     prepinfo: PrepInfo) -> Option[TypeIns]:
    if isinstance(node, ast.Assign):
        if node.type_comment:
            return eval_typedef_expr(node.type_comment, prepinfo, True)
        else:
            return Option(any_ins)

    elif isinstance(node, ast.AnnAssign):
        return eval_typedef_expr(node.annotation, prepinfo, True)

    else:
        raise TypeError("node doesn't stands for an assignment statement")


def eval_func_type(node: ast.FunctionDef,
                   prepinfo: 'PrepInfo') -> Option[TypeIns]:
    """Get a function's type according to a ast.FunctionDef node"""
    argument_option = eval_argument_type(node.args, prepinfo)
    argument = argument_option.value

    inner_sym = prepinfo.symtable.new_symtable(node.name, TableScope.FUNC)
    fun_ins = TypeFuncIns(node.name, prepinfo.symtable.glob_symid, inner_sym,
                          argument, any_ins)

    if node.returns:
        return_option = eval_typedef_expr(node.returns, prepinfo, True)
        ret_ins = return_option.value
    else:
        ret_ins = any_ins

    fun_ins = TypeFuncIns(node.name, prepinfo.symtable.glob_symid, inner_sym,
                          argument, ret_ins)
    res_option = Option(fun_ins)
    res_option.combine_error(argument_option)

    return res_option


def eval_return_type(node: Optional[TypeDefNode],
                     prepinfo: PrepInfo) -> Option[TypeIns]:
    if node:
        return eval_typedef_expr(node, prepinfo, True)

    else:
        return Option(any_ins)


def eval_argument_type(node: ast.arguments,
                       prepinfo: PrepInfo) -> Option[Argument]:
    """Gernerate an Argument instance according to an ast.arguments node"""
    new_args = Argument()
    # order_arg: [**posonlyargs, **args]
    # order_kwarg: [**kwonlyargs]
    # these two lists are created to deal with default values
    order_arg: List[Arg] = []
    order_kwarg: List[Arg] = []

    res_option = Option(new_args)

    # parse a list of args
    def add_to_list(target_list, order_list, args):
        nonlocal res_option
        for arg in args:
            option_gen_arg = eval_arg_type(arg, prepinfo)
            res_option.combine_error(option_gen_arg)
            gen_arg = option_gen_arg.value
            assert isinstance(gen_arg, Arg)
            target_list.append(gen_arg)
            order_list.append(gen_arg)

    add_to_list(new_args.posonlyargs, order_arg, node.posonlyargs)
    add_to_list(new_args.args, order_arg, node.args)
    add_to_list(new_args.kwonlyargs, order_kwarg, node.kwonlyargs)

    # *args exists
    if node.vararg:
        option_vararg = eval_arg_type(node.vararg, prepinfo)
        res_option.combine_error(option_vararg)
        result = option_vararg.value
        result.name = '*' + result.name
        new_args.vararg = result

    # **kwargs exists
    if node.kwarg:
        kwarg_option = eval_arg_type(node.kwarg, prepinfo)
        res_option.combine_error(kwarg_option)
        result = kwarg_option.value
        result.name = '**' + result.name
        new_args.kwarg = result

    for arg, value in zip(reversed(order_arg), reversed(node.defaults)):
        arg.valid = True
        arg.default = value  # TODO: add type check here

    for arg, value in zip(reversed(order_kwarg), reversed(node.kw_defaults)):
        arg.valid = True
        arg.default = value  # TODO: add type check here(here value is a node represent an expression)

    return res_option


def eval_arg_type(node: ast.arg, prepinfo: 'PrepInfo') -> Option[Arg]:
    """Generate an Arg instance according to an ast.arg node"""
    new_arg = Arg(node.arg)
    res_option = Option(new_arg)
    if node.annotation:
        ann_option = eval_typedef_expr(node.annotation, prepinfo, True)
        res_option.combine_error(ann_option)
        new_arg.ann = ann_option.value
    return res_option


TAddFunDef = Callable[[ast.FunctionDef], TypeFuncIns]
TAddFunOverload = Callable[[TypeFuncIns, Argument, TypeIns, ast.FunctionDef],
                           None]


def template_resolve_fun(prepinfo: 'PrepInfo', add_func_def: TAddFunDef,
                         add_func_overload: TAddFunOverload,
                         mbox: 'MessageBox'):
    """Template to resolve functions"""
    def get_arg_ret(node: ast.FunctionDef):
        """Get the argument and return type of the function"""
        argument_option = eval_argument_type(node.args, prepinfo)
        return_option = eval_return_type(node.returns, prepinfo)
        argument_option.dump_to_box(mbox)
        return_option.dump_to_box(mbox)
        return argument_option.value, return_option.value

    for name, entry in prepinfo.func.items():
        assert isinstance(entry, prep_func)

        overload_list = []
        not_overload = None  # function def that's not decorated by overload
        for astnode in entry.defnodes:
            is_overload = False
            for decs in astnode.decorator_list:
                if isinstance(decs, ast.Name) and decs.id == 'overload':
                    # TODO: add warning here if defined is already true before
                    is_overload = True
                    break
            if is_overload:
                overload_list.append((astnode, *get_arg_ret(astnode)))
            else:
                not_overload = astnode

        # TODO: name collision check
        if len(overload_list) > 0:
            func_ins = add_func_def(overload_list[0][0])

            for node, argument, ret_ins in overload_list[1:]:
                add_func_overload(func_ins, argument, ret_ins, node)

        else:
            assert not_overload
            add_func_def(not_overload)
