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
    WHILE = 2
    IF = 3


class BreakFlag(Enum):
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
        self.break_flag = False
        self.break_node = None

    @property
    def cur_condition(self):
        return self.reach_stack[-1]

    def accept(self, node: ast.stmt) -> Reach:
        return self.visit(node)

    def to_break(self, node: ast.stmt, flag=True):
        reach = self.reach_map.get(node)
        if not reach:
            reach = self.accept(node)
        if flag:
            return reach in REJECT_REACH
        else:
            neg_reach = cal_neg(reach)
            return neg_reach in REJECT_REACH

    def push(self, stmt: ConditionStmtType, reach: Reach):
        cur_state = self.cur_state
        if cur_state == Reach.UNKNOWN:
            self.reach_stack.append(Reach.UNKNOWN)
        elif cur_state == Reach.RUNTIME_TRUE:
            self.reach_stack.append(reach)

    def pop(self):
        self.reach_stack.pop()
        assert len(self.reach_stack) != 0

    def detect_break(self):
        return self.break_flag

    def eliminate_break(self):
        self.break_flag = False

    def get_break_node(self):
        return self.break_node

    def visit_Return(self, node: ast.Return) -> Reach:
        reach = self.cur_state
        return cal_neg(reach)

    def visit_While(self, node: ast.While) -> Reach:
        reach = self.infer_value_of_condition(node.test)
        self.reach_map[node] = reach
        if reach in ACCEPT_REACH:
            self.push(ConditionStmtType.WHILE, reach)
        return reach

    def visit_If(self, node: ast.If) -> Reach:
        reach = self.infer_value_of_condition(node.test)
        self.reach_map[node] = reach
        return reach

    def visit_Break(self, node: ast.AST):

        if self.cur_state == Reach.RUNTIME_TRUE:
            self.break_flag = True
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
        elif isinstance(test, ast.BinOp):
            pass
        elif isinstance(test, ast.Call):
            return self.infer_value_of_call(test)

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
