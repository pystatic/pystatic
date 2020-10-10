import ast
from pystatic.symtable import SymTable, TableScope, TypeDefNode
from typing import Callable, List, Optional, Union
from pystatic.visitor import BaseVisitor
from pystatic.typesys import (TypeFuncIns, TypeIns, ellipsis_type, TypeType,
                              any_type, none_type, any_ins)
from pystatic.arg import Argument, Arg
from pystatic.preprocess.sym_util import fake_fun_entry


def eval_type_expr(node: TypeDefNode,
                   symtable: SymTable) -> Optional[TypeType]:
    if isinstance(node, str):
        return eval_str_type(node, symtable)
    elif isinstance(node, ast.Assign) or isinstance(node, ast.AnnAssign):
        return eval_assign_type(node, symtable)
    elif isinstance(node, ast.FunctionDef):
        assert False, "Shouldn't reach here"
    else:
        return TypeExprVisitor(symtable).accept(node)


def eval_str_type(s: str, symtable: SymTable) -> Optional[TypeType]:
    try:
        treenode = ast.parse(s, mode='eval')
        if hasattr(treenode, 'body'):
            return TypeExprVisitor(symtable).accept(
                treenode.body)  # type: ignore
    except SyntaxError:
        return None


def eval_assign_type(node: Union[ast.Assign, ast.AnnAssign],
                     symtable: SymTable) -> Optional[TypeType]:
    if isinstance(node, ast.Assign):
        if node.type_comment:
            return eval_str_type(node.type_comment, symtable)
        else:
            return None

    elif isinstance(node, ast.AnnAssign):
        return eval_type_expr(node.annotation, symtable)

    else:
        raise TypeError("node doesn't stands for an assignment statement")


def eval_func_type(node: ast.FunctionDef,
                   symtable: SymTable) -> Optional[TypeIns]:
    """Get a function's type according to a ast.FunctionDef node"""
    argument = eval_argument_type(node.args, symtable)
    if not argument:
        return None
    ret_type = None
    if node.returns:
        ret_type = eval_type_expr(node.returns, symtable)
    if not ret_type:
        ret_type = any_type  # default return type is Any

    func_name = node.name
    inner_sym = symtable.new_symtable(func_name, TableScope.FUNC)

    return TypeFuncIns(node.name, symtable.glob_uri, inner_sym, argument,
                       ret_type)


def eval_return_type(node: Optional[TypeDefNode],
                     symtable: SymTable) -> TypeType:
    if node:
        res_type = eval_type_expr(node, symtable)
        if res_type:
            return res_type
        else:
            return any_type
    else:
        return any_type


def eval_argument_type(node: ast.arguments,
                       symtable: SymTable) -> Optional[Argument]:
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
        nonlocal ok
        for arg in args:
            gen_arg = eval_arg_type(arg, symtable)
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
        result = eval_arg_type(node.vararg, symtable)
        result.name = '*' + result.name
        if result:
            new_args.vararg = result
        else:
            ok = False

    # **kwargs exists
    if node.kwarg:
        result = eval_arg_type(node.kwarg, symtable)
        result.name = '**' + result.name
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


def eval_arg_type(node: ast.arg, symtable: SymTable) -> Optional[Arg]:
    """Generate an Arg instance according to an ast.arg node"""
    new_arg = Arg(node.arg)
    if node.annotation:
        ann = eval_type_expr(node.annotation, symtable).getins()
        if not ann:
            return None
        else:
            new_arg.ann = ann
    return new_arg


TAddFunDef = Callable[[ast.FunctionDef], TypeFuncIns]
TAddFunOverload = Callable[[TypeFuncIns, Argument, TypeIns, ast.FunctionDef],
                           None]


def template_resolve_fun(symtable: 'SymTable', add_func_define: TAddFunDef,
                         add_func_overload: TAddFunOverload):
    """Template to resolve functions"""
    def get_arg_ret(node: ast.FunctionDef):
        """Get the argument and return type of the function"""
        argument = eval_argument_type(node.args, symtable)
        ret_ins = eval_return_type(node.returns, symtable).getins()
        return argument, ret_ins

    for name, entry in symtable._func_defs.items():  # type: ignore
        entry: 'fake_fun_entry'
        assert isinstance(entry, fake_fun_entry)

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
            func_temp = add_func_define(overload_list[0][0])

            for node, argument, ret_ins in overload_list[1:]:
                add_func_overload(func_temp, argument, ret_ins, node)

        else:
            assert not_overload
            add_func_define(not_overload)


class NotType(Exception):
    pass


class InvalidAnnSyntax(Exception):
    pass


class TypeExprVisitor(BaseVisitor):
    def __init__(self, symtable: SymTable) -> None:
        self.symtable = symtable

    def visit(self, node, *args, **kwargs):
        if self.whether_visit(node):
            func = self.get_visit_func(node)
            if func == self.generic_visit:
                raise InvalidAnnSyntax
            else:
                res = func(node, *args, **kwargs)

                assert isinstance(res, TypeIns) or isinstance(res, list)
                return res

    def accept(self, node) -> Optional[TypeType]:
        try:
            res = self.visit(node)
            assert isinstance(res, TypeType)
            return res
        except NotType:
            return None  # TODO: warning?

    def visit_Attribute(self, node: ast.Attribute) -> TypeIns:
        left_type = self.visit(node.value)
        assert isinstance(left_type, TypeIns)

        res_type = left_type.getattribute(node.attr, node, None)
        # TODO: report error when res_type is not TypeIns
        assert isinstance(res_type, TypeIns)
        return res_type

    def visit_Ellipsis(self, node: ast.Ellipsis) -> TypeType:
        return ellipsis_type

    def visit_Name(self, node: ast.Name) -> TypeIns:
        res = self.symtable.lookup(node.id)
        if res:
            return res
        else:
            raise NotType

    def visit_Constant(self, node: ast.Constant) -> TypeIns:
        if node.value is Ellipsis:
            return ellipsis_type
        elif isinstance(node.value, str):
            try:
                treenode = ast.parse(node.value, mode='eval')
                if hasattr(treenode, 'body'):
                    str_res = self.visit(treenode.body)  # type: ignore
                    if not str_res:
                        raise NotType
                    else:
                        assert isinstance(str_res, TypeIns)
                        return str_res
                else:
                    raise NotType
            except SyntaxError:
                raise NotType
        elif not node.kind:
            return none_type
        else:
            raise NotType

    def visit_Subscript(self, node: ast.Subscript) -> TypeIns:
        value = self.visit(node.value)
        assert isinstance(value, TypeType)
        if isinstance(node.slice, (ast.Tuple, ast.Index)):
            if isinstance(node.slice, ast.Tuple):
                slc = self.visit(node.slice)
            else:
                # ast.Index
                slc = self.visit(node.slice.value)
            if isinstance(slc, list):
                return value.getitem(slc)[0]  # TODO: add check here
            assert isinstance(slc, TypeIns)
            return value.getitem([slc])[0]  # TODO: add check here
        else:
            assert 0, "Not implemented yet"
            raise InvalidAnnSyntax

    def visit_Tuple(self, node: ast.Tuple) -> List[TypeIns]:
        items = []
        for subnode in node.elts:
            res = self.visit(subnode)
            assert isinstance(res, TypeIns) or isinstance(res, list)
            items.append(res)
        return items

    def visit_List(self, node: ast.List) -> List[TypeIns]:
        # ast.List and ast.Tuple has similar structure
        return self.visit_Tuple(node)  # type: ignore
