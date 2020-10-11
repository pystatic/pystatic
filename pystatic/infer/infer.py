import ast
import logging
from typing import Optional
from pystatic.typesys import *
from pystatic.message import MessageBox
from pystatic.arg import Argument
from pystatic.errorcode import *
from pystatic.infer.op_map import *
from pystatic.infer.checker import TypeChecker, is_any
from pystatic.infer.visitor import BaseVisitor
from pystatic.infer.recorder import SymbolRecorder
from pystatic.exprparse import ExprParser
from pystatic.infer.displayvar import DisplayVar
from pystatic.infer import op_map

logger = logging.getLogger(__name__)


class InferVisitor(BaseVisitor):
    def __init__(self, node: ast.AST, module: TypeModuleTemp,
                 mbox: MessageBox):
        # self.cur_module: TypeModuleTemp = module
        self.root = node
        self.mbox: MessageBox = mbox
        self.checker = TypeChecker(self.mbox)

        self.recorder = SymbolRecorder(module)

        self.ret_list = []
        self.ret_annotation = None

    def infer(self):
        self.visit(self.root)
        DisplayVar(self.recorder).accept(self.root)

    @property
    def cur_type(self):
        return self.recorder.cur_type

    def type_consistent(self, ltype, rtype):
        return self.checker.check(ltype, rtype)

    def get_type(self, node):
        return ExprParser(self.mbox, self.recorder).parse_expr(node)

    def visit_Assign(self, node: ast.Assign):
        rtype = self.get_type(node.value)
        if rtype is None:  # some wrong with rvalue
            return
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.infer_name_node_of_assign(target, node.value, rtype)
            elif isinstance(target, (ast.List, ast.Tuple)):
                self.check_multi_left_of_assign(target.elts, node.value, rtype)
            else:
                self.check_composed_node_of_assign(target, node.value, rtype)

    def infer_name_node_of_assign(self, target, rnode, rtype):
        if self.recorder.is_defined(target.id):
            ltype = self.cur_type.lookup_local_var(target.id)
        else:  # var appear first time
            self.recorder.add_symbol(target.id)
            ltype = self.cur_type.lookup_local_var(target.id)
            if is_any(ltype):  # var with no annotation
                self.cur_type.setattr(target.id, rtype)
        if not self.type_consistent(ltype, rtype):
            self.mbox.incompatible_type_in_assign(rnode, ltype, rtype)

    def check_composed_node_of_assign(self, target, rnode, rtype):
        ltype = self.get_type(target)
        if not ltype:
            return
        if not self.type_consistent(ltype, rtype):
            self.mbox.incompatible_type_in_assign(rnode, ltype, rtype)

    def check_multi_left_of_assign(self, target, rnode, rtypes):
        if len(target) < len(rtypes):
            self.mbox.need_more_values_to_unpack(rnode)
        elif len(target) > len(rtypes):
            self.mbox.too_more_values_to_unpack(rnode)
        for lvalue, node, rtype in zip(target, rnode.elts, rtypes):
            if isinstance(lvalue, ast.Name):
                self.infer_name_node_of_assign(lvalue, node, rtype)
            elif isinstance(lvalue, (ast.List, ast.Tuple)):
                self.check_multi_left_of_assign(lvalue.elts, node, rtype)
            else:
                self.check_composed_node_of_assign(lvalue, node, rtype)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        rtype: Optional[TypeIns] = self.get_type(node.value)
        if rtype is None:
            return
        target = node.target
        if isinstance(target, ast.Name):
            self.check_name_node_of_annassign(target, node.value, rtype)
        else:
            self.check_composed_node_of_assign(target, node.value, rtype)

    def check_name_node_of_annassign(self, target, rnode, rtype):
        if not self.recorder.is_defined(target.id):  # var appear first time
            self.recorder.add_symbol(target.id)
        ltype = self.cur_type.lookup_local_var(target.id)
        if not self.type_consistent(ltype, rtype):
            self.mbox.incompatible_type_in_assign(rnode, ltype, rtype)

    def check_composed_node_of_annassign(self, target, rnode, rtype):
        self.check_composed_node_of_assign(target, rnode, rtype)

    def visit_AugAssign(self, node: ast.AugAssign):
        ltype = self.get_type(node.target)
        rtype = self.get_type(node.value)
        func_name = op_map.binop_map[type(node.op)]
        func_type = ltype.getattribute(func_name)
        operand = op_map.binop_char_map[type(node.op)]
        if func_type is None:
            self.mbox.unsupported_operand(node.target, operand, ltype, rtype)
        self.check_operand(node.value, func_type, operand, ltype, rtype)

    def check_operand(self, node, func_type, operand, ltype, rtype):
        # TODO:revise call
        argument, ret = func_type.call(None)
        assert len(argument.args) == 2
        if not self.type_consistent(argument.args[1].ann, rtype):
            self.mbox.unsupported_operand(node, operand, ltype, rtype)

    def visit_ClassDef(self, node: ast.ClassDef):
        self.recorder.add_symbol(node.name)
        class_type = self.cur_type.lookup_local_var(node.name)
        self.recorder.enter_cls(class_type)
        for subnode in node.body:
            self.visit(subnode)
        self.recorder.leave_cls()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.recorder.add_symbol(node.name)
        func_type: TypeIns = self.cur_type.lookup_local_var(node.name)
        argument, self.ret_annotation = func_type.call(
            None)  # TODO: need modify on overload func

        self.recorder.enter_func(func_type, self.infer_argument(argument))
        for subnode in node.body:
            self.visit(subnode)
        self.infer_ret_value_of_func(func_type, node.returns)
        self.recorder.leave_func()

    def infer_argument(self, argument: Argument):
        # TODO: default value
        args = {}
        for arg in argument.posonlyargs:
            args[arg.name] = arg.ann
        for arg in argument.args:
            args[arg.name] = arg.ann
        for arg in argument.kwonlyargs:
            args[arg.name] = arg.ann
        kwargs = argument.kwarg
        if kwargs:
            args[kwargs.name] = kwargs.ann
        vararg = argument.vararg
        if vararg:
            args[vararg.name] = vararg.ann
        return args

    def infer_ret_value_of_func(self, func_type, type_comment):
        if len(self.ret_list) == 0:
            rtype = none_type
            if not is_any(self.ret_annotation):
                self.mbox.return_value_expected(type_comment)
        elif len(self.ret_list) == 1:
            # TODO
            rtype = self.ret_list[0]
            if rtype is None:
                rtype = none_type
        else:
            # TODO
            pass
        self.ret_list = []
        if not is_any(self.ret_annotation):
            func_type.ret_type = rtype

    def visit_Return(self, node: ast.Return):
        ret_type = self.get_type(node.value)
        self.check_ret_type(self.ret_annotation, node, ret_type)
        self.ret_list.append(ret_type)

    def check_ret_type(self, annotation, ret_node: ast.Return, ret_type):
        if ret_type is None:
            self.mbox.return_value_expected(ret_node)
            return
        if not self.type_consistent(annotation, ret_type):
            self.mbox.incompatible_return_type(ret_node.value, annotation,
                                               ret_type)

    def visit_While(self, node: ast.While):
        pass

    def visit_If(self, node: ast.If):
        cond = self.get_type(node.test)
        for subnode in node.body:
            self.visit(subnode)
        self.visit(node.orelse)



class InferStarter:
    def __init__(self, sources, mbox):
        self.sources = sources
        self.mbox = mbox

    def start_infer(self):
        for uri, target in self.sources.items():
            logger.info(f'Type infer in module \'{uri}\'')
            tp = target.module_temp.lookup_local_var('f1')
            print(type(tp))
            infer_visitor = InferVisitor(target.ast, target.module_temp,
                                         self.mbox)
            infer_visitor.infer()
