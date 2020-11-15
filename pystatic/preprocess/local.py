import ast
from collections import deque
from inspect import isbuiltin
from typing import Deque
from pystatic.arg import Argument
from pystatic.symtable import SymTable
from pystatic.typesys import TypeClassTemp, any_ins, TypeIns
from pystatic.predefined import TypeFuncIns
from pystatic.symtable import Entry
from pystatic.message import MessageBox
from pystatic.preprocess.def_expr import (eval_func_type, eval_typedef_expr,
                                          template_resolve_fun)
from pystatic.preprocess.prepinfo import *


def resolve_local_typeins(target: 'BlockTarget', env: 'PrepEnvironment',
                          mbox: 'MessageBox'):
    """Resolve local symbols' TypeIns"""
    def resolve_def(prepinfo: 'PrepInfo', entry: 'prep_local_def'):
        nonlocal mbox
        assert isinstance(entry, prep_local_def)
        defnode = entry.defnode
        tpins_option = eval_typedef_expr(defnode, prepinfo)
        entry.value = tpins_option.value
        tpins_option.dump_to_box(mbox)

    init_prepinfo = env.get_target_prepinfo(target)
    assert init_prepinfo
    queue: Deque[PrepInfo] = deque()
    queue.append(init_prepinfo)

    while len(queue):
        cur_prepinfo = queue.popleft()
        for _, entry in cur_prepinfo.local.items():
            resolve_def(cur_prepinfo, entry)

        if isinstance(cur_prepinfo, MethodPrepInfo):
            for _, entry in cur_prepinfo.var_attr.items():
                resolve_def(cur_prepinfo, entry)

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
