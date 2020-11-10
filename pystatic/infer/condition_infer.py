import ast
from typing import Dict, Union, List
from enum import Enum
from pystatic.exprparse import eval_expr
from pystatic.option import Option
from pystatic.visitor import val_unparse, VisitException
from pystatic.message import ErrorMaker
from pystatic.predefined import TypeLiteralIns
from pystatic.errorcode import *
from pystatic.config import Config
from pystatic.infer.recorder import SymbolRecorder
from pystatic.infer.visitor import BaseVisitor
from pystatic.infer.reachability import Reach, cal_neg, ACCEPT_REACH, REJECT_REACH, is_true
from pystatic.TypeCompatibe.simpleType import type_consistent


class ConditionStmtType(Enum):
    GLOBAL = 1
    LOOP = 2
    IF = 3
    FUNC = 4


class BreakFlag(Enum):
    NORMAL = 0
    RETURN = 1
    BREAK = 2
    CONTINUE = 3


class Condition:
    def __init__(self, stmt_type: ConditionStmtType, reach: Reach):
        self.stmt_type = stmt_type
        self.reach = reach


class ConditionInfer(BaseVisitor):
    def __init__(self,
                 recorder: SymbolRecorder,
                 err_maker: ErrorMaker,
                 config: Config) -> None:
        super().__init__()
        self.recorder = recorder
        self.reach_map: Dict[ast.stmt, Reach] = {}
        self.err_maker = err_maker
        self.config = config
        self.reach_stack: List[Condition] = [
            Condition(ConditionStmtType.GLOBAL, Reach.ALWAYS_TRUE)
        ]
        self.break_flag = BreakFlag.NORMAL
        self.break_node: Optional[ast.stmt] = None

    @property
    def cur_condition(self):
        return self.reach_stack[-1]

    def accept(self, node: ast.stmt):
        self.visit(node)

    def rejected(self):
        reach = self.cur_condition.reach
        return reach in REJECT_REACH

    def pop(self):
        self.reach_stack.pop()
        assert len(self.reach_stack) != 0

    def flip(self):
        self.reach_stack[-1].stmt_type = ConditionStmtType.IF
        self.reach_stack[-1].reach = cal_neg(self.reach_stack[-1].reach)

    def detect_break(self):
        return self.break_flag != BreakFlag.NORMAL

    def eliminate_break(self, outer_state):
        if self.break_flag == BreakFlag.BREAK or self.break_flag == BreakFlag.CONTINUE:
            if outer_state != ConditionStmtType.IF:
                self.break_flag = BreakFlag.NORMAL
            else:
                if self.cur_condition.reach == Reach.UNKNOWN:
                    self.break_flag = BreakFlag.NORMAL
        elif self.break_flag == BreakFlag.RETURN:
            if outer_state == ConditionStmtType.FUNC:
                self.break_flag = BreakFlag.NORMAL
            elif self.cur_condition.reach == Reach.UNKNOWN:
                self.break_flag = BreakFlag.NORMAL

    def get_break_node(self):
        return self.break_node

    def mark_node(self, node: ast.stmt, reach: Reach):
        self.reach_map[node] = reach
        node.reach = reach

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.reach_stack.append(
            Condition(ConditionStmtType.FUNC, Reach.ALWAYS_TRUE))

    def visit_While(self, node: ast.While):
        reach = self.infer_value_of_condition(node.test)
        self.mark_node(node, reach)
        self.reach_stack.append(Condition(ConditionStmtType.LOOP, reach))

    def visit_If(self, node: ast.If):
        reach = self.infer_value_of_condition(node.test)
        self.mark_node(node, reach)
        self.reach_stack.append(Condition(ConditionStmtType.IF, reach))

    def visit_Break(self, node: ast.Break):
        self.break_flag = BreakFlag.BREAK
        self.break_node = node

    def visit_Continue(self, node: ast.Continue):
        self.break_flag = BreakFlag.CONTINUE
        self.break_node = node

    def visit_Return(self, node: ast.Return):
        self.break_flag = BreakFlag.RETURN
        self.break_node = node

    def infer_value_of_condition(self, test: ast.expr) -> Reach:
        if isinstance(test, ast.Constant):
            res = self.infer_value_of_constant(test)
            return res
        elif isinstance(test, ast.UnaryOp):
            op = test.op
            if isinstance(op, (ast.Not, ast.USub)):
                return cal_neg(self.infer_value_of_condition(test.operand))
            elif isinstance(op, ast.UAdd):
                return self.infer_value_of_condition(test.operand)
            else:
                assert False, "TODO"
        elif isinstance(test, ast.Compare):
            left = test.left
            for cmpa, op in zip(test.comparators, test.ops):
                right = cmpa
                if is_cmp_python_version(left):
                    res = compare_python_version(left, right, op, self.config, False)
                elif is_cmp_python_version(right):
                    res = compare_python_version(right, left, op, self.config, True)
                else:
                    return Reach.UNKNOWN
                if not is_true(res, False):
                    return res
                left = cmpa
            return Reach.ALWAYS_TRUE
        elif isinstance(test, ast.BoolOp):
            op = test.op
            if isinstance(op, ast.And):
                for value in test.values:
                    value_reach = self.infer_value_of_condition(value)
                    if value_reach == Reach.ALWAYS_FALSE:
                        return Reach.ALWAYS_FALSE
                    elif value_reach == Reach.UNKNOWN:
                        return Reach.UNKNOWN
                return Reach.ALWAYS_TRUE
            elif isinstance(op, test.Or):
                for value in test.values:
                    value_reach = self.infer_value_of_condition(value)
                    if value_reach == Reach.ALWAYS_TRUE:
                        return Reach.ALWAYS_TRUE
                    elif value_reach == Reach.UNKNOWN:
                        return Reach.UNKNOWN
                return Reach.ALWAYS_FALSE
            else:
                assert False, "not reach here"
        elif isinstance(test, ast.Call):
            return self.infer_value_of_call(test)
        elif isinstance(test, ast.Name):
            return self.infer_value_of_name_node(test)
        else:
            return Reach.UNKNOWN

    def infer_value_of_call(self, test: ast.Call) -> Reach:
        if isinstance(test.func, ast.Name):
            name = test.func.id
            args = test.args
            if name == "isinstance":
                # option = eval_expr(test, self.recorder)
                # if self.err_maker.exsit_error(option):
                #     self.err_maker.dump_option(option)
                first_type = self.err_maker.dump_option(
                    eval_expr(args[0], self.recorder))
                second_type = self.err_maker.dump_option(
                    eval_expr(args[1], self.recorder))
                if type_consistent(
                        first_type,
                        self.err_maker.dump_option(second_type.call(None))):
                    return Reach.ALWAYS_TRUE
                else:
                    return Reach.ALWAYS_FALSE
                # TODO
            elif name == "issubclass":
                pass

    def infer_value_of_constant(self, test: ast.Constant) -> Reach:
        option: Option = eval_expr(test, self.recorder)
        literal_ins: TypeLiteralIns = self.err_maker.dump_option(option)
        if self.err_maker.exsit_error(option):
            return Reach.UNKNOWN
        if literal_ins.value:
            return Reach.ALWAYS_TRUE
        else:
            return Reach.ALWAYS_FALSE

    def infer_value_of_name_node(self, test: ast.Name):
        option: Option = eval_expr(test, self.recorder)
        tp = self.err_maker.dump_option(option)
        if self.err_maker.exsit_error(option):
            return Reach.UNKNOWN
        if isinstance(tp, TypeLiteralIns):
            if tp.value:
                return Reach.ALWAYS_TRUE
            else:
                return Reach.ALWAYS_FALSE
        else:
            return Reach.UNKNOWN


def is_cmp_python_version(node: ast.expr):
    if (isinstance(node, ast.Attribute) and node.attr == 'version_info'
            and isinstance(node.value, ast.Name) and node.value.id == 'sys'):
        return True
    else:
        return False


def compare_python_version(sys_node: ast.expr,
                           cmp_node: ast.expr,
                           op: ast.cmpop,
                           config: 'Config',
                           atright=False) -> Reach:
    py_version = config.python_version
    try:
        right = val_unparse(cmp_node)
    except VisitException:
        return Reach.UNKNOWN
    if not isinstance(right, tuple):
        return Reach.UNKNOWN

    left = py_version
    if atright:
        left, right = right, left

    cond_map = {False: Reach.ALWAYS_FALSE, True: Reach.ALWAYS_TRUE}
    if isinstance(op, ast.Eq):
        return cond_map[left == right]
    elif isinstance(op, ast.Gt):
        return cond_map[left > right]
    elif isinstance(op, ast.GtE):
        return cond_map[left >= right]
    elif isinstance(op, ast.Lt):
        return cond_map[left < right]
    elif isinstance(op, ast.LtE):
        return cond_map[left <= right]
    else:
        return Reach.UNKNOWN
