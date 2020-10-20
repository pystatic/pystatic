import ast
from typing import Dict, Union, List
from pystatic.infer.reachability import Reach, cal_neg
from pystatic.config import Config
from pystatic.exprparse import eval_expr
from pystatic.option import Option
from pystatic.message import ErrorMaker
from pystatic.typesys import TypeLiteralIns
from pystatic.infer.recorder import SymbolRecorder
from pystatic.infer.visitor import BaseVisitor
from pystatic.errorcode import *
from pystatic.TypeCompatibe.simpleType import is_any, type_consistent


class ConditionInfer(BaseVisitor):


    def __init__(self,
                 recorder: SymbolRecorder,
                 reach_map: Dict[ast.AST, Reach],
                 err_maker: ErrorMaker):
        super().__init__()
        self.recorder = recorder
        self.reach_map = reach_map
        self.err_maker = err_maker
        self.reach_stack: List[Reach] = [Reach.RUNTIME_TRUE]

    @property
    def cur_state(self):
        return self.reach_stack[-1]

    def pop(self):
        self.reach_stack.pop()
        assert len(self.reach_stack) != 0

    def accept(self, condition: ast.AST):
        return self.visit(condition)

    def visit_Return(self, node: ast.Return) -> Reach:
        reach = self.cur_state
        return cal_neg(reach)

    def visit_While(self, node: ast.While) -> Reach:
        reach = self.infer_value_of_condition(node.test)
        if reach in ACCEPT_REACH:
            self.reach_stack.append(reach)
        return reach

    def visit_If(self, node: ast.If) -> Reach:
        reach = self.infer_value_of_condition(node.test)
        return reach

    def infer_value_of_condition(self, test: ast.expr):
        if isinstance(test, ast.Constant):
            return self.infer_value_of_constant(test)
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
