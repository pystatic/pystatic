import ast
from collections import deque
from typing import Deque
from pystatic.arg import Argument
from pystatic.typesys import TypeIns
from pystatic.predefined import TypeFuncIns, TypeVarTemp
from pystatic.message import MessageBox
from pystatic.exprparse import eval_expr
from pystatic.preprocess.def_expr import (eval_func_type, eval_typedef_expr,
                                          template_resolve_fun)
from pystatic.preprocess.prepinfo import *
from pystatic.preprocess.util import omit_inst_typetype


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

def judge_typealias(prepinfo: 'PrepInfo', node: AssignNode) -> Optional[TypeType]:
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
                    prepinfo.add_type_alias(target.id, typetype, node)
                    return typetype
                else:
                    raise NotImplementedError()
    return None


def resolve_local_typeins(target: 'BlockTarget', env: 'PrepEnvironment',
                          mbox: 'MessageBox'):
    """Resolve local symbols' TypeIns"""
    def judge_spt_def(prepinfo: 'PrepInfo', entry: 'prep_local'):
        if (typevar := judge_typevar(prepinfo, entry.defnode)):
            entry.value = typevar
            return True
        elif (typetype := judge_typealias(prepinfo, entry.defnode)):
            entry.value = TypeAlias(entry.name, typetype)
            return True
        return False

    def resolve_def(prepinfo: 'PrepInfo', entry: 'prep_local', attr: bool):
        nonlocal mbox
        assert isinstance(entry, prep_local)
        defnode = entry.defnode
        # won't check special type definition for attribution definitions
        if attr or not judge_spt_def(prepinfo, entry):
            tpins_option = eval_typedef_expr(defnode, prepinfo, False)
            entry.value = tpins_option.value
            tpins_option.dump_to_box(mbox)

    init_prepinfo = env.get_target_prepinfo(target)
    assert init_prepinfo
    queue: Deque[PrepInfo] = deque()
    queue.append(init_prepinfo)

    while len(queue):
        cur_prepinfo = queue.popleft()
        for _, entry in cur_prepinfo.local.items():
            resolve_def(cur_prepinfo, entry, False)

        if isinstance(cur_prepinfo, MethodPrepInfo):
            for _, entry in cur_prepinfo.var_attr.items():
                resolve_def(cur_prepinfo, entry, True)

        for clsdef in cur_prepinfo.cls_def.values():
            queue.append(clsdef.prepinfo)


def resolve_local_func(target: 'BlockTarget', env: 'PrepEnvironment',
                       mbox: 'MessageBox'):
    """Resolve local function's TypeIns"""
    prepinfo = env.get_target_prepinfo(target)
    assert prepinfo

    def add_func_def(node: ast.FunctionDef):
        nonlocal prepinfo, mbox
        assert prepinfo

        func_option = eval_func_type(node, prepinfo)
        func_ins = func_option.value
        assert isinstance(func_ins, TypeFuncIns)

        func_option.dump_to_box(mbox)
        name = node.name

        func_entry = prepinfo.func[name]
        assert not func_entry.value
        func_entry.value = func_ins
        return func_ins

    def add_func_overload(func_ins: TypeFuncIns, argument: Argument,
                          ret: TypeIns, node: ast.FunctionDef):
        func_ins.add_overload(argument, ret)

    template_resolve_fun(prepinfo, add_func_def, add_func_overload, mbox)
