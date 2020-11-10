import ast
import logging
from contextlib import contextmanager
from typing import Optional, Set
from pystatic.typesys import *
from pystatic.predefined import *
from pystatic.message import MessageBox, ErrorMaker
from pystatic.arg import Argument
from pystatic.errorcode import *
from pystatic.exprparse import eval_expr
from pystatic.option import Option
from pystatic.opmap import *
from pystatic.config import Config
from pystatic.infer.visitor import BaseVisitor
from pystatic.infer.recorder import SymbolRecorder
from pystatic.infer.condition_infer import ConditionInfer, ConditionStmtType
from pystatic.TypeCompatibe.simpleType import TypeCompatible, is_any, type_consistent

logger = logging.getLogger(__name__)


class InferVisitor(BaseVisitor):
    def __init__(self, node: ast.AST, module: TypeModuleTemp,
                 mbox: MessageBox, config: Config):
        self.root = node
        self.mbox = mbox
        self.err_maker = ErrorMaker(mbox)
        self.type_comparator = TypeCompatible()
        self.recorder = SymbolRecorder(module)
        self.config = config
        self.cond_infer = ConditionInfer(self.recorder, self.err_maker, self.config)

    def infer(self):
        self.visit(self.root)

    def get_type(self, node: Optional[ast.AST]) -> TypeIns:
        option = eval_expr(node, self.recorder)
        option.dump_to_box(self.mbox)
        return option.value

    def set_type(self, name: str, cur_type: TypeIns):
        self.cond_infer.save_type(name)
        self.recorder.set_type(name, cur_type)

    def type_consistent(self, ltype: TypeIns, rtype: TypeIns) -> bool:
        return type_consistent(ltype, rtype)

    def visit_Assign(self, node: ast.Assign):
        rtype = self.get_type(node.value)
        self.err_maker.add_type(node.value, rtype)  # TODO:plugin
        for target in node.targets:
            self.err_maker.add_type(target, rtype)  # plugin
            if isinstance(target, ast.Name):
                self.infer_name_node_of_assign(target, rtype, node.value)
            elif isinstance(target, (ast.List, ast.Tuple)):
                self.check_multi_left_of_assign(target.elts, rtype, node.value)
            else:
                self.check_composed_node_of_assign(target, rtype, node.value)

    def infer_name_node_of_assign(self, target: ast.Name, rtype: TypeIns,
                                  rnode: ast.AST):
        name = target.id
        comment = self.recorder.get_comment_type(name)
        if not self.recorder.is_defined(name):
            self.recorder.set_type(target.id, comment)
        if not self.type_consistent(comment, rtype):
            self.set_type(name, comment)
            self.err_maker.add_err(
                IncompatibleTypeInAssign(rnode, comment, rtype))
        else:
            self.set_type(name, rtype)

    def check_composed_node_of_assign(self, target: ast.AST, rtype: TypeIns,
                                      rnode: Optional[ast.AST]):
        ltype = self.get_type(target)
        if not self.type_consistent(ltype, rtype):
            self.err_maker.add_err(
                IncompatibleTypeInAssign(rnode, ltype, rtype))

    def check_multi_left_of_assign(self, target: List[ast.expr],
                                   rtype: TypeIns, rnode: Optional[ast.AST]):
        type_list = rtype.bindlist
        if not type_list:  # a,b=()
            self.err_maker.add_err(
                NeedMoreValuesToUnpack(rnode, len(target), 0))
            return
        if not isinstance(rnode, (ast.Tuple, ast.List)):  # a,b=1
            self.err_maker.add_err(
                NeedMoreValuesToUnpack(rnode, len(target), 1))
            return
        if len(target) < len(type_list):
            self.err_maker.add_err(
                NeedMoreValuesToUnpack(rnode, len(target), len(type_list)))
            return
        elif len(target) > len(type_list):
            self.err_maker.add_err(
                TooMoreValuesToUnpack(rnode, len(target), len(type_list)))
            return
        for lvalue, tp, node in zip(target, type_list, rnode.elts):
            if isinstance(lvalue, ast.Name):
                self.infer_name_node_of_assign(lvalue, rtype, node)
            elif isinstance(lvalue, (ast.List, ast.Tuple)):
                self.check_multi_left_of_assign(lvalue.elts, rtype, node)
            else:
                self.check_composed_node_of_assign(lvalue, rtype, node)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        rtype: TypeIns = self.get_type(node.value)
        self.err_maker.add_type(node.target, rtype)  # TODO:plugin
        self.err_maker.add_type(node.value, rtype)
        target = node.target
        if isinstance(target, ast.Name):
            self.check_name_node_of_annassign(target, rtype, node.value)
        else:
            self.check_composed_node_of_annassign(target, rtype, node.value)

    def check_name_node_of_annassign(self, target: ast.Name, rtype, rnode):
        name = target.id
        comment = self.recorder.get_comment_type(name)
        if not self.recorder.is_defined(name):  # var appear first time
            self.recorder.set_type(name, comment)

        if not self.type_consistent(comment, rtype):
            self.err_maker.add_err(
                IncompatibleTypeInAssign(rnode, comment, rtype))
            self.set_type(name, comment)
        else:
            self.set_type(name, rtype)

    def check_composed_node_of_annassign(self, target: ast.AST, rtype: TypeIns,
                                         rnode: Optional[ast.AST]):
        self.check_composed_node_of_assign(target, rtype, rnode)

    def visit_AugAssign(self, node: ast.AugAssign):
        ltype = self.get_type(node.target)
        rtype = self.get_type(node.value)
        func_name: str = binop_map[type(node.op)]
        option: Option = ltype.getattribute(func_name, None)
        operand = binop_char_map[type(node.op)]
        if self.err_maker.exsit_error(option):
            self.err_maker.add_err(
                UnsupportedBinOperand(node.target, operand, ltype, rtype))
            return
        func_type = self.err_maker.dump_option(option)
        self.check_arg_of_operand_func(node.value, func_type, operand, ltype,
                                       rtype)

    def check_arg_of_operand_func(self, node, func_type, operand, ltype,
                                  rtype):
        apply_args = ApplyArgs()
        apply_args.add_arg(rtype, node)
        option: Option = func_type.call(apply_args)
        if self.err_maker.exsit_error(option):
            self.err_maker.add_err(
                UnsupportedBinOperand(node, operand, ltype, rtype))

    @contextmanager
    def visit_scope(self, node):
        tp = self.recorder.get_comment_type(node.name)
        self.recorder.set_type(node.name, tp)
        yield tp
        self.recorder.leave_scope()

    def visit_ClassDef(self, node: ast.ClassDef):
        with self.visit_scope(node) as class_type:
            self.recorder.enter_cls(class_type)
            for subnode in node.body:
                self.visit(subnode)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        with self.visit_condition(node):
            with self.visit_scope(node) as func_type:
                argument, ret_annotation = func_type.get_func_def()
                self.recorder.enter_func(func_type,
                                         self.infer_argument(argument),
                                         ret_annotation)
                self.accept_condition_stmt_list(node.body,
                                                ConditionStmtType.FUNC)

                self.infer_return_value_of_func(node.returns)

    def infer_argument(self, argument: Argument):
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

    def infer_return_value_of_func(self, node):
        ret_set = self.recorder.get_ret_type()
        ret_list = list(ret_set)
        ret_annotation = self.recorder.get_ret_annotation()
        num = len(ret_list)
        if num == 0:
            self.err_maker.add_err(ReturnValueExpected(node))
        else:
            # TODO
            pass

    def visit_Return(self, node: ast.Return):
        self.cond_infer.accept(node)
        ret_type = self.get_type(node.value)
        ret_annotation = self.recorder.get_ret_annotation()
        self.check_ret_type(ret_annotation, node, ret_type)
        self.recorder.add_ret(ret_type)

    def check_ret_type(self, annotation, ret_node: ast.Return, ret_type):
        if not self.type_consistent(annotation, ret_type):
            self.err_maker.add_err(
                IncompatibleReturnType(ret_node.value, annotation, ret_type))

    def accept_condition_stmt_list(self, stmt_list: List[ast.stmt], stmt_type):
        for stmt in stmt_list:
            if self.cond_infer.detect_break():
                index = stmt_list.index(stmt)
                self.err_maker.generate_code_unreachable_error(
                    stmt_list[index:])
                break
            self.visit(stmt)

        self.cond_infer.eliminate_break(stmt_type)

    def visit_stmt_after_condition(self, stmt_list, condition_type):
        if not self.cond_infer.rejected():
            self.accept_condition_stmt_list(stmt_list, condition_type)
        else:
            self.err_maker.generate_code_unreachable_error(stmt_list)

    @contextmanager
    def visit_condition(self, node):
        self.cond_infer.accept(node)
        yield
        self.cond_infer.pop()

    def visit_While(self, node: ast.While):
        with self.visit_condition(node):
            self.visit_stmt_after_condition(node.body, ConditionStmtType.LOOP)
            self.cond_infer.flip()
            self.visit_stmt_after_condition(node.orelse, ConditionStmtType.IF)

    def visit_If(self, node: ast.If):
        with self.visit_condition(node):
            self.visit_stmt_after_condition(node.body, ConditionStmtType.IF)
            if node.orelse:
                self.cond_infer.flip()
                self.visit_stmt_after_condition(node.orelse, ConditionStmtType.IF)

    def visit_Break(self, node: ast.Break):
        self.cond_infer.accept(node)

    def visit_Continue(self, node: ast.Continue):
        self.cond_infer.accept(node)

    def visit_For(self, node: ast.For):
        container = self.get_type(node.iter)
        get_element_type_in_container(container)

def get_element_type_in_container(container: TypeIns):
    print(container)
    print(container.bindlist)



class InferStarter:
    def __init__(self, sources, config):
        self.sources = sources
        self.config = config

    def start_infer(self):
        for symid, target in self.sources.items():
            logger.info(f'Type infer in module \'{symid}\'')
            infer_visitor = InferVisitor(target.ast, target.module_temp,
                                         target.mbox, self.config)
            infer_visitor.infer()
