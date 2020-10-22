import ast
from typing import Dict, Union, List
from enum import Enum
from pystatic.exprparse import eval_expr
from pystatic.option import Option
from pystatic.message import ErrorMaker
from pystatic.typesys import TypeLiteralIns
from pystatic.errorcode import *
from pystatic.infer.recorder import SymbolRecorder
from pystatic.infer.visitor import BaseVisitor
from pystatic.infer.reachability import Reach, cal_neg, ACCEPT_REACH, REJECT_REACH


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
                 # reach_map: Dict[ast.AST, Reach],
                 err_maker: ErrorMaker):
        super().__init__()
        self.recorder = recorder
        self.reach_map: Dict[ast.stmt, Reach] = {}
        self.err_maker = err_maker
        self.reach_stack: List[Condition] = [Condition(ConditionStmtType.GLOBAL,
                                                       Reach.RUNTIME_TRUE)]
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
                # print("ejre")
                self.break_flag = BreakFlag.NORMAL

    def get_break_node(self):
        return self.break_node

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.reach_stack.append(Condition(ConditionStmtType.FUNC, Reach.RUNTIME_TRUE))

    def visit_While(self, node: ast.While):
        reach = self.infer_value_of_condition(node.test)
        self.reach_map[node] = reach
        self.reach_stack.append(Condition(ConditionStmtType.LOOP, reach))

    def visit_If(self, node: ast.If):
        reach = self.infer_value_of_condition(node.test)
        self.reach_map[node] = reach
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
        elif isinstance(test, ast.Call):
            return self.infer_value_of_call(test)
        else:
            return Reach.UNKNOWN

    def infer_value_of_call(self, test: ast.Call) -> Reach:
        if isinstance(test.func, ast.Name):
            name = test.func.id
            args = test.args
            if name == "isinstance":
                option = eval_expr(test, self.recorder)
                if self.err_maker.exsit_error(option):
                    self.err_maker.dump_option(option)
                first_type = self.err_maker.dump_option(eval_expr(args[0], self.recorder))
                second_type = self.err_maker.dump_option(eval_expr(args[1], self.recorder))
                pass
            elif name == "issubclass":
                pass

    def infer_value_of_constant(self, test: ast.Constant) -> Reach:
        option: Option = eval_expr(test, self.recorder)
        literal_ins: TypeLiteralIns = self.err_maker.dump_option(option)
        if self.err_maker.exsit_error(option):
            return Reach.UNKNOWN
        if literal_ins.value:
            return Reach.RUNTIME_TRUE
        else:
            return Reach.RUNTIME_FALSE
