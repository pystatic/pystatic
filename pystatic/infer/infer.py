import ast
import logging
from typing import Optional, Set
from pystatic.typesys import *
from pystatic.message import MessageBox, ErrorMaker
from pystatic.arg import Argument
from pystatic.errorcode import *
from pystatic.exprparse import eval_expr
from pystatic.option import Option
from pystatic.infer.op_map import *
from pystatic.infer.visitor import BaseVisitor
from pystatic.infer.recorder import SymbolRecorder
from pystatic.infer import op_map
from pystatic.infer.condition_infer import ConditionInfer, ConditionStmtType
from pystatic.TypeCompatibe.simpleType import TypeCompatible, is_any, type_consistent

logger = logging.getLogger(__name__)


class InferVisitor(BaseVisitor):
    def __init__(self, node: ast.AST, module: TypeModuleTemp,
                 mbox: MessageBox):
        self.root = node
        self.err_maker = ErrorMaker(mbox)
        self.type_comparator = TypeCompatible()
        self.recorder = SymbolRecorder(module)
        self.cond_infer = ConditionInfer(self.recorder, self.err_maker)

    def infer(self):
        self.visit(self.root)

    def get_type(self, node: ast.AST) -> TypeIns:
        option = eval_expr(node, self.recorder)
        self.err_maker.handle_err(option.errors)
        return option.value

    def type_consistent(self, ltype: TypeIns, rtype: TypeIns) -> bool:
        return type_consistent(ltype, rtype)

    def visit_Assign(self, node: ast.Assign):
        rtype = self.get_type(node.value)
        self.err_maker.add_type(node.value, rtype)
        for target in node.targets:
            self.err_maker.add_type(target, rtype)  # TODO
            if isinstance(target, ast.Name):
                self.infer_name_node_of_assign(target, node.value, rtype)
            elif isinstance(target, (ast.List, ast.Tuple)):
                self.check_multi_left_of_assign(target.elts, node.value, rtype)
            else:
                self.check_composed_node_of_assign(target, node.value, rtype)

    def infer_name_node_of_assign(self, target: ast.Name, rnode: ast.AST,
                                  rtype: TypeIns):
        name = target.id
        comment = self.recorder.get_comment_type(name)
        if not self.recorder.is_defined(name):
            self.recorder.set_type(target.id, comment)
        if not self.type_consistent(comment, rtype):
            self.err_maker.add_err(
                IncompatibleTypeInAssign(rnode, comment, rtype))
        else:
            self.recorder.set_type(target.id, rtype)

    def check_composed_node_of_assign(self, target: ast.AST, rnode: ast.AST,
                                      rtype: TypeIns):
        ltype = self.get_type(target)

        if not self.type_consistent(ltype, rtype):
            self.err_maker.add_err(
                IncompatibleTypeInAssign(rnode, ltype, rtype))

    def check_multi_left_of_assign(self, target: List[ast.AST], rnode, rtypes):
        if len(target) < len(rtypes):
            self.err_maker.add_err(NeedMoreValuesToUnpack(rnode))
        elif len(target) > len(rtypes):
            self.err_maker.add_err(TooMoreValuesToUnpack(rnode))
        for lvalue, node, rtype in zip(target, rnode.elts, rtypes):
            if isinstance(lvalue, ast.Name):
                self.infer_name_node_of_assign(lvalue, node, rtype)
            elif isinstance(lvalue, (ast.List, ast.Tuple)):
                self.check_multi_left_of_assign(lvalue.elts, node, rtype)
            else:
                self.check_composed_node_of_assign(lvalue, node, rtype)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        rtype: Optional[TypeIns] = self.get_type(node.value)
        self.err_maker.add_type(node.target, rtype)
        self.err_maker.add_type(node.value, rtype)
        target = node.target
        if isinstance(target, ast.Name):
            self.check_name_node_of_annassign(target, node.value, rtype)
        else:
            self.check_composed_node_of_assign(target, node.value, rtype)

    def check_name_node_of_annassign(self, target: ast.Name, rnode, rtype):
        name = target.id
        comment = self.recorder.get_comment_type(name)
        if not self.recorder.is_defined(name):  # var appear first time
            self.recorder.set_type(name, comment)

        if not self.type_consistent(comment, rtype):
            self.err_maker.add_err(IncompatibleTypeInAssign(rnode, comment, rtype))
            self.recorder.set_type(name, comment)
        else:
            self.recorder.set_type(name, rtype)

    def check_composed_node_of_annassign(self, target: ast.AST, rnode: ast.AST,
                                         rtype: TypeIns):
        self.check_composed_node_of_assign(target, rnode, rtype)

    def visit_AugAssign(self, node: ast.AugAssign):
        ltype = self.get_type(node.target)
        rtype = self.get_type(node.value)
        func_name: str = op_map.binop_map[type(node.op)]
        option: Option = ltype.getattribute(func_name, None)
        operand = op_map.binop_char_map[type(node.op)]
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

    def visit_ClassDef(self, node: ast.ClassDef):
        class_type = self.recorder.get_comment_type(node.name)
        self.recorder.set_type(node.name, class_type)
        self.recorder.enter_cls(class_type)
        for subnode in node.body:
            self.visit(subnode)
        self.recorder.leave_cls()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.cond_infer.accept(node)

        func_type: TypeIns = self.recorder.get_comment_type(node.name)
        self.recorder.set_type(node.name, func_type)
        argument, ret_annotation = self.err_maker.dump_option(
            func_type.call(None))
        self.recorder.enter_func(func_type, self.infer_argument(argument),
                                 ret_annotation)
        self.accept_condition_stmt_list(node.body, ConditionStmtType.FUNC)

        self.infer_return_value_of_func(node.returns)
        self.recorder.leave_func()
        self.cond_infer.pop()

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

    def visit_While(self, node: ast.While):
        self.cond_infer.accept(node)
        if not self.cond_infer.rejected():
            self.accept_condition_stmt_list(node.body, ConditionStmtType.LOOP)
        else:
            self.err_maker.generate_code_unreachable_error(node.body)

        self.cond_infer.flip()

        if not self.cond_infer.rejected():
            self.accept_condition_stmt_list(node.orelse,
                                            ConditionStmtType.LOOP)
        else:
            self.err_maker.generate_code_unreachable_error(node.orelse)
        self.cond_infer.pop()

    def visit_If(self, node: ast.If):
        self.cond_infer.accept(node)
        if not self.cond_infer.rejected():
            self.accept_condition_stmt_list(node.body, ConditionStmtType.IF)
        else:
            self.err_maker.generate_code_unreachable_error(node.body)

        self.cond_infer.flip()

        if not self.cond_infer.rejected():
            self.accept_condition_stmt_list(node.orelse, ConditionStmtType.IF)
        else:
            self.err_maker.generate_code_unreachable_error(node.orelse)
        self.cond_infer.pop()

    def visit_Break(self, node: ast.Break):
        self.cond_infer.accept(node)

    def visit_Continue(self, node: ast.Continue):
        self.cond_infer.accept(node)


class InferStarter:
    def __init__(self, sources):
        self.sources = sources

    def start_infer(self):
        for symid, target in self.sources.items():
            logger.info(f'Type infer in module \'{symid}\'')
            print(
                target.module_temp.getattribute('A',
                                                None).getattribute('hj',
                                                                   None).value)
            infer_visitor = InferVisitor(target.ast, target.module_temp,
                                         target.mbox)
            infer_visitor.infer()
