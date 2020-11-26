import ast
from collections import deque
from typing import Deque, Callable
from pystatic.arg import Argument
from pystatic.typesys import TypeIns
from pystatic.predefined import TypeFuncIns, TypeVarTemp
from pystatic.message import MessageBox
from pystatic.exprparse import eval_expr
from pystatic.preprocess.def_expr import (eval_func_type, eval_typedef_expr,
                                          eval_argument_type, eval_return_type)
from pystatic.preprocess.util import omit_inst_typetype
from pystatic.preprocess.prepinfo import *


def judge_typevar(prepinfo: 'PrepInfo', node: AssignNode):
    def get_name(node: ast.AST) -> Optional[str]:
        if isinstance(node, ast.Name):
            return node.id
        return None

    value_node = node.value
    if isinstance(value_node, ast.Call):
        f_ins = eval_expr(value_node.func, prepinfo).value
        if isinstance(f_ins, TypeType) and isinstance(f_ins.temp, TypeVarTemp):
            if isinstance(node, ast.AnnAssign):
                typevar_name = get_name(node)
                assert typevar_name  # TODO: error
            elif isinstance(node, ast.Assign):
                assert node.targets[0]  # TODO: error
                typevar_name = get_name(node.targets[0])
                assert typevar_name  # TODO: error
            else:
                raise TypeError()
            typevar = TypeVarIns(typevar_name)
            prepinfo.add_typevar_def(typevar_name, typevar, node)
            return typevar
    return None

def judge_typealias(prepinfo: 'PrepInfo', node: AssignNode) -> Optional[TypeAlias]:
    if isinstance(node, ast.AnnAssign):
        # assignment with type annotation is not a type alias.
        return None

    if node.value:
        typetype = omit_inst_typetype(node.value, prepinfo, False)
        if typetype:
            if isinstance(typetype, tuple):
                raise NotImplementedError()
            else:
                if len(node.targets) != 1:
                    return None
                else:
                    target = node.targets[0]
            
                if isinstance(target, ast.Name):
                    typealias = TypeAlias(target.id, typetype)
                    prepinfo.add_type_alias(target.id, typealias, node)
                    return typealias
                else:
                    raise NotImplementedError()
    return None


def resolve_local(local: 'prep_local'):
    """Resolve local symbols' TypeIns"""
    assert isinstance(local, prep_local)
    defnode = local.defnode
    prepinfo = local.def_prepinfo
    
    if (typevar := judge_typevar(prepinfo, local.defnode)):
        local.value = typevar
    elif (typealias := judge_typealias(prepinfo, local.defnode)):
        local.value = typealias
    else:
        tpins_option = eval_typedef_expr(defnode, local.def_prepinfo, False)
        local.value = tpins_option.value


def resolve_func(func: 'prep_func'):
    """Resolve local function's TypeIns"""
    def add_func_def(node: ast.FunctionDef):
        nonlocal func
        func_option = eval_func_type(node, func.def_prepinfo)
        func_ins = func_option.value
        assert isinstance(func_ins, TypeFuncIns)

        assert not func.value
        func.value = func_ins
        return func_ins

    def add_func_overload(func_ins: TypeFuncIns, argument: Argument,
                          ret: TypeIns, node: ast.FunctionDef):
        func_ins.add_overload(argument, ret)

    symid = func.def_prepinfo.glob_symid
    resolve_func_template(func, add_func_def, add_func_overload, MessageBox(symid))


TAddFunDef = Callable[[ast.FunctionDef], TypeFuncIns]
TAddFunOverload = Callable[[TypeFuncIns, Argument, TypeIns, ast.FunctionDef],
                           None]


def resolve_func_template(func: 'prep_func', add_func_def: TAddFunDef,
                         add_func_overload: TAddFunOverload,
                         mbox: 'MessageBox'):
    """Template to resolve functions"""
    prepinfo = func.def_prepinfo
    def get_arg_ret(node: ast.FunctionDef):
        """Get the argument and return type of the function"""
        nonlocal prepinfo
        argument_option = eval_argument_type(node.args, prepinfo)
        return_option = eval_return_type(node.returns, prepinfo)
        argument_option.dump_to_box(mbox)
        return_option.dump_to_box(mbox)
        return argument_option.value, return_option.value

    overload_list = []
    not_overload = None  # function def that's not decorated by overload
    for astnode in func.defnodes:
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
