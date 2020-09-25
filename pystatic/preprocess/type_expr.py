import ast
from pystatic.symtable import SymTable, TypeDefNode
from typing import List, Optional, Union
from pystatic.visitor import BaseVisitor
from pystatic.typesys import (TypeFuncTemp, TypeIns, ellipsis_type, TypeType,
                              any_type)
from pystatic.arg import Argument, Arg


def eval_type_expr(node: TypeDefNode,
                   symtable: SymTable) -> Optional[TypeType]:
    if isinstance(node, str):
        return eval_str_type(node, symtable)
    elif isinstance(node, ast.Assign) or isinstance(node, ast.AnnAssign):
        return eval_assign_type(node, symtable)
    elif isinstance(node, ast.FunctionDef):
        return eval_func_type(node, symtable)
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
                   symtable: SymTable) -> Optional[TypeType]:
    """Get a function's type according to a ast.FunctionDef node"""
    argument = eval_argument_type(node.args, symtable)
    if not argument:
        return None
    ret_type = None
    if node.returns:
        ret_type = eval_type_expr(node.returns, symtable)
    if not ret_type:
        ret_type = any_type  # default return type is Any
    return TypeFuncTemp(node.name, argument, ret_type).get_default_type()


def eval_arg_type(node: ast.arg, symtable: SymTable) -> Optional[Arg]:
    """Generate an Arg instance according to an ast.arg node"""
    new_arg = Arg(node.arg)
    if node.annotation:
        ann = eval_type_expr(node.annotation, symtable)
        if not ann:
            return None
        else:
            new_arg.ann = ann
    return new_arg


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
        global ok
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
        if result:
            new_args.vararg = result
        else:
            ok = False

    # **kwargs exists
    if node.kwarg:
        result = eval_arg_type(node.kwarg, symtable)
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

                assert isinstance(res, TypeType) or isinstance(res, list)
                return res

    def accept(self, node) -> Optional[TypeType]:
        try:
            res = self.visit(node)
            assert isinstance(res, TypeType)
            return res
        except NotType:
            return None  # TODO: warning?

    def visit_Attribute(self, node: ast.Attribute) -> TypeType:
        left_type = self.visit(node.value)

        assert isinstance(left_type, TypeType)

        res_type = left_type.getattribute(node.attr)
        # TODO: report error when res_type is not TypeIns
        assert isinstance(res_type, TypeType)
        return res_type

    def visit_Ellipsis(self, node: ast.Ellipsis) -> TypeType:
        return ellipsis_type

    def visit_Name(self, node: ast.Name) -> TypeType:
        res = self.symtable.lookup(node.id)
        if res:
            assert isinstance(res, TypeType)
            return res
        else:
            raise NotType

    def visit_Constant(self, node: ast.Constant) -> TypeType:
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
                        return str_res
                else:
                    raise NotType
            except SyntaxError:
                raise NotType
        else:
            raise NotType

    def visit_Subscript(self, node: ast.Subscript) -> TypeType:
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
            assert isinstance(slc, TypeType)
            return value.getitem([slc])[0]  # TODO: add check here
        else:
            assert 0, "Not implemented yet"
            raise InvalidAnnSyntax

    def visit_Tuple(self, node: ast.Tuple) -> List[TypeType]:
        items = []
        for subnode in node.elts:
            res = self.visit(subnode)
            assert isinstance(res, TypeIns) or isinstance(res, list)
            items.append(res)
        return items

    def visit_List(self, node: ast.List) -> List[TypeType]:
        # ast.List and ast.Tuple has similar structure
        return self.visit_Tuple(node)  # type: ignore
