import ast
from typing import Dict
from pystatic.reach import Reach, cal_neg
from pystatic.config import Config
from pystatic.exprparse import eval_expr
from pystatic.option import Option
from pystatic.message import ErrorMaker
from pystatic.typesys import TypeLiteralIns
from pystatic.infer.recorder import SymbolRecorder
from pystatic.errorcode import *


class ConditionInfer:
    def __init__(self,
                 recorder: SymbolRecorder,
                 reach_map: Dict[ast.expr, Reach],
                 err_maker: ErrorMaker):
        self.recorder = recorder
        self.reach_map = reach_map
        self.err_maker = err_maker

    def infer_value_of_condition(self, test: ast.expr, config: Config):
        if isinstance(test, ast.Constant):
            return self.infer_value_of_constant(test)
        elif isinstance(test, ast.UnaryOp):
            op = test.op
            if isinstance(op, (ast.Not, ast.USub)):
                return cal_neg(self.infer_value_of_condition(test.operand, config))
            elif isinstance(op, ast.UAdd):
                return self.infer_value_of_condition(test.operand, config)
            else:
                assert False, "TODO"
        elif isinstance(test, ast.Call):
            return self.infer_value_of_call(test)

    def infer_value_of_call(self, test: ast.Call) -> Reach:
        if isinstance(test.func, ast.Name):
            name = test.func.id
            if name == "isinstance":
                args = test.args
                if len(args) <= 1:
                    self.err_maker.add_err(TooFewArgument(test, name))

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
