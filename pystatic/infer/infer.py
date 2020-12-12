import ast
import logging
from contextlib import contextmanager
from typing import Optional, Deque, TYPE_CHECKING
from pystatic.typesys import *
from pystatic.predefined import *
from pystatic.target import FunctionTarget, Target, BlockTarget
from pystatic.message import MessageBox, ErrorMaker
from pystatic.arg import Argument
from pystatic.errorcode import *
from pystatic.exprparse import eval_expr
from pystatic.option import Option
from pystatic.opmap import *
from pystatic.config import Config
from pystatic.visitor import BaseVisitor
from pystatic.infer.recorder import SymbolRecorder
from pystatic.infer.condition_infer import ConditionInfer, ConditionStmtType
from pystatic.TypeCompatible.simpleType import (
    TypeCompatible,
    is_any,
    is_none,
    type_consistent,
)

if TYPE_CHECKING:
    from pystatic.manager import Manager
    from pystatic.symid import SymId

logger = logging.getLogger(__name__)


class InferVisitor(BaseVisitor):
    def __init__(
        self,
        node: ast.AST,
        module: TypeModuleIns,
        mbox: MessageBox,
        symid: "SymId",
        config: Config,
        manager: "Manager",
    ):
        self.root = node
        self.mbox = mbox
        self.symid = symid
        self.err_maker = ErrorMaker(self.mbox)
        self.type_comparator = TypeCompatible()
        self.recorder = SymbolRecorder(module)
        self.config = config
        self.cond_infer = ConditionInfer(self.recorder, self.err_maker, self.config)
        self.manager = manager

    def infer(self):
        self.visit(self.root)

    def get_type(self, node: Optional[ast.AST]) -> TypeIns:
        option = eval_expr(node, self.recorder)
        option.dump_to_box(self.mbox)
        return option.value

    def record_type(self, name: str, cur_type: TypeIns):
        self.cond_infer.save_type(name)
        self.recorder.record_type(name, cur_type)

    def type_consistent(self, ltype: TypeIns, rtype: TypeIns) -> bool:
        return type_consistent(ltype, rtype)

    def visit_Assign(self, node: ast.Assign):
        rtype = self.get_type(node.value)
        setattr(node, "type", rtype)
        for target in node.targets:
            setattr(node, "type", rtype)
            if isinstance(target, ast.Name):
                self.infer_name_node_of_assign(target, rtype, node.value)
            elif isinstance(target, (ast.List, ast.Tuple)):
                self.check_multi_left_of_assign(target.elts, rtype, node.value)
            else:
                self.check_composed_node_of_assign(target, rtype, node.value)

    def infer_name_node_of_assign(
        self, target: ast.Name, rtype: TypeIns, rnode: ast.AST
    ):
        name = target.id
        comment = self.recorder.get_comment_type(name)
        if not self.recorder.is_defined(name):
            self.recorder.record_type(target.id, comment)
        if not self.type_consistent(comment, rtype):
            self.err_maker.add_err(IncompatibleTypeInAssign(rnode, comment, rtype))
        else:
            self.record_type(name, rtype)

    def check_composed_node_of_assign(
        self, target: ast.AST, rtype: TypeIns, rnode: Optional[ast.AST]
    ):
        ltype = self.get_type(target)
        if not self.type_consistent(ltype, rtype):
            self.err_maker.add_err(IncompatibleTypeInAssign(rnode, ltype, rtype))

    def check_multi_left_of_assign(
        self, target: List[ast.expr], rtype: TypeIns, rnode: Optional[ast.AST]
    ):
        type_list = rtype.bindlist
        if not type_list:  # a,b=()
            self.err_maker.add_err(NeedMoreValuesToUnpack(rnode, len(target), 0))
            return
        if not isinstance(rnode, (ast.Tuple, ast.List)):  # a,b=1
            self.err_maker.add_err(NeedMoreValuesToUnpack(rnode, len(target), 1))
            return
        if len(target) < len(type_list):
            self.err_maker.add_err(
                TooMoreValuesToUnpack(rnode, len(target), len(type_list))
            )
        elif len(target) > len(type_list):
            self.err_maker.add_err(
                NeedMoreValuesToUnpack(rnode, len(target), len(type_list))
            )
        for lvalue, tp, node in zip(target, type_list, rnode.elts):
            if isinstance(lvalue, ast.Name):
                self.infer_name_node_of_assign(lvalue, tp, node)
            elif isinstance(lvalue, (ast.List, ast.Tuple)):
                self.check_multi_left_of_assign(lvalue.elts, tp, node)
            else:
                self.check_composed_node_of_assign(lvalue, tp, node)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        if node.value is None:
            self.record_no_value_node(node.target)
            return
        rtype: TypeIns = self.get_type(node.value)
        setattr(node.value, "type", rtype)
        target = node.target
        if isinstance(target, ast.Name):
            self.check_name_node_of_annassign(target, rtype, node.value)
        else:
            self.check_composed_node_of_annassign(target, rtype, node.value)

    def record_no_value_node(self, target: ast.Name):
        assert isinstance(target, ast.Name)
        name = target.id
        comment = self.recorder.get_comment_type(name)
        self.recorder.record_type(name, comment)

    def check_name_node_of_annassign(self, target: ast.Name, rtype, rnode):
        name = target.id
        comment = self.recorder.get_comment_type(name)
        setattr(target, "type", comment)
        if not self.recorder.is_defined(name):  # var appear first time
            self.recorder.record_type(name, comment)

        if not self.type_consistent(comment, rtype):
            self.err_maker.add_err(IncompatibleTypeInAssign(rnode, comment, rtype))
        else:
            self.record_type(name, rtype)

    def check_composed_node_of_annassign(
        self, target: ast.AST, rtype: TypeIns, rnode: Optional[ast.AST]
    ):
        self.check_composed_node_of_assign(target, rtype, rnode)

    def visit_AugAssign(self, node: ast.AugAssign):
        ltype = self.get_type(node.target)
        rtype = self.get_type(node.value)
        func_name: str = binop_map[type(node.op)]
        option: Option = ltype.getattribute(func_name, None)
        operand = binop_char_map[type(node.op)]
        if self.err_maker.exsit_error(option):
            self.err_maker.add_err(
                UnsupportedBinOperand(node.target, operand, ltype, rtype)
            )
            return
        func_type = self.err_maker.dump_option(option)
        self.check_arg_of_operand_func(node.value, func_type, operand, ltype, rtype)

    def check_arg_of_operand_func(self, node, func_type, operand, ltype, rtype):
        apply_args = ApplyArgs()
        apply_args.add_arg(rtype, node)
        option: Option = func_type.call(apply_args)
        if self.err_maker.exsit_error(option):
            self.err_maker.add_err(UnsupportedBinOperand(node, operand, ltype, rtype))

    @contextmanager
    def visit_scope(self, node):
        tp = self.recorder.get_comment_type(node.name)
        self.recorder.record_type(node.name, tp)
        setattr(node, "type", tp)
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
                self.preprocess_in_func(node, func_type)
                argument, ret_annotation = func_type.get_func_def()
                self.recorder.enter_func(
                    func_type, self.infer_argument(argument), ret_annotation
                )
                self.accept_condition_stmt_list(node.body, ConditionStmtType.FUNC)

                self.infer_return_value_of_func(node.returns)
                self.recorder.clear_ret_val()

    def preprocess_in_func(self, node: ast.FunctionDef, func_type: TypeFuncIns):
        new_table = func_type.get_inner_symtable()
        func_target = FunctionTarget(self.symid, new_table, node, self.mbox)
        self.manager.preprocess_block(func_target)

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

    def infer_return_value_of_func(self, node: ast.AST):
        ret_set = self.recorder.get_ret_type()
        ret_list = list(ret_set)
        ret_annotation = self.recorder.get_ret_annotation()
        num = len(ret_list)
        if is_any(ret_annotation):
            self.recorder.reset_ret_val()
            return
        if num == 0 and not is_none(ret_annotation):
            self.err_maker.add_err(ReturnValueExpected(node))

    def visit_Return(self, node: ast.Return):
        self.cond_infer.accept(node)
        ret_type = self.get_type(node.value)
        ret_annotation = self.recorder.get_ret_annotation()
        self.check_ret_type(ret_annotation, node, ret_type)
        self.recorder.add_ret(ret_type)

    def check_ret_type(
        self, annotation: TypeIns, ret_node: ast.Return, ret_type: TypeIns
    ):
        if not self.type_consistent(annotation, ret_type):
            if is_none(ret_type):
                self.err_maker.add_err(ReturnValueExpected(ret_node))
            else:
                self.err_maker.add_err(
                    IncompatibleReturnType(ret_node.value, annotation, ret_type)
                )

    def accept_condition_stmt_list(
        self,
        stmt_list: List[ast.stmt],
        stmt_type: ConditionStmtType,
        ignore_error=False,
    ):
        for stmt in stmt_list:
            if self.cond_infer.detect_break():
                index = stmt_list.index(stmt)
                if not ignore_error:
                    self.err_maker.generate_code_unreachable_error(stmt_list[index:])
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
        error_format = False
        container = self.get_type(node.iter)
        if not self.check_iterable(node.iter, container):
            error_format = True
        if not isinstance(node.target, ast.Name):
            # TODO: raise error
            pass
        else:
            name = node.target.id
            if error_format:
                bindlist = [any_ins]
            else:
                bindlist = self.get_element_type_in_container(container)
            self.record_type(name, bindlist[0])
            self.accept_condition_stmt_list(node.body, ConditionStmtType.LOOP)
            self.accept_condition_stmt_list(node.orelse, ConditionStmtType.IF)
            if len(bindlist) > 1:
                for tp in bindlist[1:]:
                    self.record_type(name, tp)
                    self.accept_condition_stmt_list(
                        node.body, ConditionStmtType.LOOP, True
                    )
                    self.accept_condition_stmt_list(
                        node.orelse, ConditionStmtType.IF, True
                    )

    def visit_Expr(self, node: ast.Expr):
        self.get_type(node)

    def get_element_type_in_container(self, container: TypeIns) -> List[TypeIns]:
        name = container.temp.name
        if name == "Dict":
            return [container.bindlist[0]]
        else:
            return container.bindlist

    def check_iterable(self, node: ast.AST, container: TypeIns) -> bool:
        # TODO: change to __iter__
        if is_any(container):
            return False
        if container.bindlist is None:
            self.err_maker.add_err(NonIterative(node, container))
            return False
        return True


class InferStarter:
    def __init__(self, q_infer: Deque[BlockTarget], config: Config, manager: "Manager"):
        self.q_infer = q_infer
        self.config = config
        self.manager = manager

    def start_infer(self):
        for target in self.q_infer:
            symid = target.symid
            logger.info(f"Type infer in module '{symid}'")
            assert isinstance(target, Target)
            infer_visitor = InferVisitor(
                target.ast,
                target.module_ins,
                target.mbox,
                symid,
                self.config,
                self.manager,
            )
            infer_visitor.infer()
        self.q_infer.clear()
