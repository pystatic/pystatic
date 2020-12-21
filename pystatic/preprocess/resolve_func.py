import ast
from typing import Callable
from pystatic.predefined import TypeFuncIns, TypeIns
from pystatic.error.errorbox import ErrorBox
from pystatic.arg import Argument, Arg
from pystatic.typesys import any_ins
from pystatic.infer.infer_expr import infer_expr_ann
from pystatic.preprocess.prepinfo import *


def resolve_func(func: "prep_func"):
    """Resolve local function's TypeIns"""

    def add_func_def(
        argument: Argument, ret: TypeIns, node: ast.FunctionDef
    ) -> TypeFuncIns:
        nonlocal func
        def_symtable = func.def_prepinfo.symtable
        module_symid = def_symtable.glob_symid
        fun_name = func.name
        new_symtable = def_symtable.new_symtable(fun_name, TableScope.FUNC)
        return TypeFuncIns(fun_name, module_symid, new_symtable, argument, ret)

    def add_func_overload(
        func_ins: TypeFuncIns, argument: Argument, ret: TypeIns, node: ast.FunctionDef
    ):
        func_ins.add_overload(argument, ret)

    errbox = func.def_prepinfo.errbox
    resolve_func_template(func, add_func_def, add_func_overload, errbox)


TAddFunDef = Callable[[Argument, TypeIns, ast.FunctionDef], TypeFuncIns]
TAddFunOverload = Callable[[TypeFuncIns, Argument, TypeIns, ast.FunctionDef], None]
FunTuple = Tuple[Argument, TypeIns, ast.FunctionDef]


def resolve_func_template(
    func: "prep_func",
    add_func_def: TAddFunDef,
    add_func_overload: TAddFunOverload,
    errbox: "ErrorBox",
):
    prepinfo = func.def_prepinfo

    def get_arg_ret(node: ast.FunctionDef):
        """Get the argument and return type of the function"""
        nonlocal prepinfo
        argument_result = eval_argument_type(node.args, prepinfo)
        return_result = eval_return_type(node.returns, prepinfo)
        argument_result.dump_to_box(errbox)
        return_result.dump_to_box(errbox)
        return argument_result.value, return_result.value

    overload_list: List[FunTuple] = []
    not_overload: Optional[
        FunTuple
    ] = None  # function def that's not decorated by overload
    for astnode in func.defnodes:
        is_overload = False
        for decs in astnode.decorator_list:
            if getattr(decs, "id", None) == "overload":
                is_overload = True
                break
        if is_overload:
            overload_list.append((*get_arg_ret(astnode), astnode))
        else:
            if not_overload:
                overload_list.append((*get_arg_ret(astnode), astnode))
                errbox.add_err(SymbolRedefine(astnode, func.name, not_overload[-1]))
                setattr(astnode, "reach", Reach.REDEFINE)
            else:
                not_overload = (*get_arg_ret(astnode), astnode)

    len_overload = len(overload_list)
    if len_overload > 0:
        if not_overload:
            func_ins = add_func_def(*not_overload)
            start = 0
        else:
            func_ins = add_func_def(*overload_list[0])
            start = 1

        for i in range(start, len_overload):
            argument, ret_ins, node = overload_list[i]
            add_func_overload(func_ins, argument, ret_ins, node)

    else:
        assert not_overload
        func_ins = add_func_def(*not_overload)
    func.value = func_ins


def eval_argument_type(node: ast.arguments, prepinfo: PrepInfo) -> Result[Argument]:
    """Gernerate an Argument instance according to an ast.arguments node"""
    errbox = prepinfo.errbox
    new_args = Argument()
    # order_arg: [**posonlyargs, **args]
    # order_kwarg: [**kwonlyargs]
    # these two lists are created to deal with default values
    order_arg: List[Arg] = []
    order_kwarg: List[Arg] = []

    result = Result(new_args)

    def resolve_arg_type(node: ast.arg) -> Arg:
        """Generate an Arg instance according to an ast.arg node"""
        nonlocal errbox, prepinfo
        new_arg = Arg(node.arg, any_ins)
        if node.annotation:
            ann_result = infer_expr_ann(node.annotation, prepinfo)
            ann_result.dump_to_box(errbox)
            new_arg.ann = ann_result.value
        return new_arg

    # parse a list of args
    def add_to_list(target_list: List[Arg], order_list: List[Arg], args: List[ast.arg]):
        nonlocal result
        for arg in args:
            newarg = resolve_arg_type(arg)
            assert isinstance(newarg, Arg)
            target_list.append(newarg)
            order_list.append(newarg)

    add_to_list(new_args.posonlyargs, order_arg, node.posonlyargs)
    add_to_list(new_args.args, order_arg, node.args)
    add_to_list(new_args.kwonlyargs, order_kwarg, node.kwonlyargs)

    # star at the start of the name is not stored for *args and **kwargs
    if node.vararg:
        vararg = resolve_arg_type(node.vararg)
        new_args.vararg = vararg
    if node.kwarg:
        kwarg = resolve_arg_type(node.kwarg)
        new_args.kwarg = kwarg

    for arg, value in zip(reversed(order_arg), reversed(node.defaults)):
        arg.valid = True
        arg.default = value  # TODO: add type check here

    for arg, value in zip(reversed(order_kwarg), reversed(node.kw_defaults)):
        arg.valid = True
        arg.default = value  # TODO: add type check here(here value is a node represent an expression)

    return result


def eval_return_type(node, prepinfo: PrepInfo) -> Result[TypeIns]:
    if node:
        return infer_expr_ann(node, prepinfo)
    else:
        return Result(any_ins)
