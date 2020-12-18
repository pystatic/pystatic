from enum import Enum
from typing import Dict
from pystatic.exprparse import eval_expr
from pystatic.result import Result
from pystatic.predefined import TypeLiteralIns
from pystatic.config import Config
from pystatic.infer.staticinfer import cmp_by_op
from pystatic.infer.recorder import SymbolRecorder, StoredType
from pystatic.visitor import BaseVisitor
from pystatic.reach import Reach, cal_neg, is_true
from pystatic.TypeCompatible.simpleType import type_consistent
from pystatic.typesys import TypeIns
from pystatic.error.errorbox import ErrorBox
from pystatic.error.errorcode import *


def level_error_in_result(result: Result):
    if result.errors:
        for err in result.errors:
            if err.level == Level.ERROR:
                return True
    return False


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
        self.dirty_map: Dict[str, StoredType] = {}


class ConditionInfer(BaseVisitor):
    def __init__(
        self,
        recorder: SymbolRecorder,
        errbox: ErrorBox,
        config: Config,
    ) -> None:
        super().__init__()
        self.recorder = recorder
        self.reach_map: Dict[ast.stmt, Reach] = {}
        self.errbox = errbox
        self.config = config
        self.reach_stack: List[Condition] = [
            Condition(ConditionStmtType.GLOBAL, Reach.ALWAYS_TRUE)
        ]
        self.break_flag = BreakFlag.NORMAL
        self.break_node: Optional[ast.stmt] = None
        self.isinstance_cond = False
        self.temp_type: Dict[str, StoredType] = {}

    def dump_result(self, result: Result):
        result.dump_to_box(self.errbox)
        return result.value

    @property
    def cur_condition(self):
        return self.reach_stack[-1]

    def save_type(self, name: str, is_permanent=True):
        tp = self.recorder.get_run_time_type(name)
        self.cur_condition.dirty_map[name] = StoredType(tp, is_permanent)

    def accept(self, node: ast.stmt, *args, **kwargs):
        self.visit(node)

    def rejected(self):
        reach = self.cur_condition.reach
        return reach in (Reach.ALWAYS_FALSE, Reach.TYPE_FALSE)

    def pop(self):
        self.recover_type()
        self.reach_stack.pop()
        assert len(self.reach_stack) != 0

    def recover_type(self):
        if self.cur_condition.reach == Reach.UNKNOWN or self.isinstance_cond:
            if self.isinstance_cond:
                self.isinstance_cond = False
                self.cur_condition.dirty_map.update(self.temp_type)
                self.temp_type.clear()
            self.recorder.recover_type(self.cur_condition.dirty_map)

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
        setattr(node, "reach", reach)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.reach_stack.append(Condition(ConditionStmtType.FUNC, Reach.ALWAYS_TRUE))

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
        if hasattr(test, "reach"):
            res = test.reach
            assert res != Reach.UNKNOWN
            return res
        if isinstance(test, ast.Constant):
            return self.infer_value_of_constant(test)
        elif isinstance(test, ast.UnaryOp):
            return self.infer_value_of_unary_op(test)
        elif isinstance(test, ast.Compare):
            return self.infer_value_of_compare(test)
        elif isinstance(test, ast.BoolOp):
            return self.infer_value_of_bool_op(test)
        elif isinstance(test, ast.Call):
            return self.infer_value_of_call(test)
        elif isinstance(test, ast.Name):
            return self.infer_value_of_name_node(test)
        else:
            return Reach.UNKNOWN

    def infer_value_of_call(self, test: ast.Call) -> Reach:
        if isinstance(test.func, ast.Name):
            name = test.func.id
            if name == "isinstance":
                return self.visit_isinstance(test)
            elif name == "issubclass":
                return self.visit_issubclass(test)
        return Reach.UNKNOWN

    def visit_isinstance(self, node: ast.Call) -> Reach:
        args = node.args
        first_type = self.dump_result(eval_expr(args[0], self.recorder))
        second_typetype = self.dump_result(eval_expr(args[1], self.recorder))
        result = second_typetype.call(None, node)
        name = args[0].id
        if result.haserr():
            assert "TODO"
        second_type = result.value
        if type_consistent(first_type, second_type):
            if isinstance(args[0], ast.Name):
                pre_type = self.recorder.get_run_time_type(name)
                self.temp_type[name] = StoredType(pre_type, False)
                self.recorder.record_type(name, second_type)
                self.isinstance_cond = True
            if first_type.temp.name == "Union":
                return Reach.UNKNOWN
            else:
                return Reach.ALWAYS_TRUE
        else:
            return Reach.ALWAYS_FALSE

    def visit_issubclass(self, node: ast.Call) -> Reach:
        # TODO
        return Reach.UNKNOWN

    def infer_value_of_constant(self, test: ast.Constant) -> Reach:
        result: Result = eval_expr(test, self.recorder)
        literal_ins: TypeLiteralIns = self.dump_result(result)
        if result.haserr():
            return self.dispose_error_condition(result)
        if literal_ins.value:
            return Reach.ALWAYS_TRUE
        else:
            return Reach.ALWAYS_FALSE

    def infer_value_of_unary_op(self, test: ast.UnaryOp) -> Reach:
        op = test.op
        res = self.infer_value_of_condition(test.operand)
        if isinstance(op, ast.Not):
            return cal_neg(res)
        elif isinstance(op, ast.UAdd):
            return res
        elif isinstance(op, ast.USub):
            if isinstance(test.operand, ast.Constant):  # -1 1 0 -0
                return res
            else:  # -False -True
                return cal_neg(res)
        else:
            return Reach.UNKNOWN

    def infer_value_of_bool_op(self, test: ast.BoolOp) -> Reach:
        op = test.op
        if isinstance(op, ast.And):
            return self.infer_value_of_and_op(test)
        elif isinstance(op, ast.Or):
            return self.infer_value_of_or_op(test)
        else:
            assert False, "not reach here"

    def infer_value_of_and_op(self, test: ast.BoolOp) -> Reach:
        for value in test.values:
            value_reach = self.infer_value_of_condition(value)
            if value_reach == Reach.ALWAYS_FALSE:
                return Reach.ALWAYS_FALSE
            elif value_reach == Reach.UNKNOWN:
                return Reach.UNKNOWN
        return Reach.ALWAYS_TRUE

    def infer_value_of_or_op(self, test: ast.BoolOp) -> Reach:
        for value in test.values:
            value_reach = self.infer_value_of_condition(value)
            if value_reach == Reach.ALWAYS_TRUE:
                return Reach.ALWAYS_TRUE
            elif value_reach == Reach.UNKNOWN:
                return Reach.UNKNOWN
        return Reach.ALWAYS_FALSE

    def infer_value_of_name_node(self, test: ast.Name) -> Reach:
        if test.id == "TYPE_CHECKING":
            return Reach.TYPE_TRUE
        result: Result = eval_expr(test, self.recorder)
        tp = self.dump_result(result)
        if result.haserr():
            return self.dispose_error_condition(result)
        if isinstance(tp, TypeLiteralIns):
            if tp.value:
                return Reach.ALWAYS_TRUE
            else:
                return Reach.ALWAYS_FALSE
        else:
            return Reach.UNKNOWN

    def infer_value_of_compare(self, test: ast.Compare) -> Reach:
        left = test.left
        for cmpa, op in zip(test.comparators, test.ops):
            right = cmpa
            res = self.get_value_of_compare(left, right, op)
            if not is_true(res, False):
                return res
            left = cmpa
        return Reach.ALWAYS_TRUE

    def get_value_of_compare(
        self, left: ast.expr, right: ast.expr, op: ast.cmpop
    ) -> Reach:
        # TODO: modify after eval_expr suppose compare
        result: Result = eval_expr(left, self.recorder)
        left_tp = self.dump_result(result)
        if result.haserr():
            return self.dispose_error_condition(result)
        result = eval_expr(right, self.recorder)
        right_tp = self.dump_result(result)
        if result.haserr():
            return self.dispose_error_condition(result)
        if self.is_cmp_between_constant(left_tp, right_tp):
            return cmp_by_op(left_tp.value, right_tp.value, op)
        else:
            return Reach.UNKNOWN

    def dispose_error_condition(self, result: Result) -> Reach:
        if level_error_in_result(result):
            return Reach.ALWAYS_FALSE
        else:
            return Reach.UNKNOWN

    def is_cmp_between_constant(self, left: TypeIns, right: TypeIns) -> bool:
        if isinstance(left, TypeLiteralIns) and isinstance(right, TypeLiteralIns):
            return True
        return False
