import ast
from pystatic.typesys import TypeIns, TypeType
from pystatic.option import Option
from pystatic.exprparse import ExprParser, SupportGetAttribute, eval_expr


def eval_preptype(
    node: ast.AST, consultant: SupportGetAttribute, annotation: bool, shallow: bool
):
    return PrepTypeEvaluator(consultant, annotation, shallow).accept(node)


def eval_expr_ann(node: ast.AST, consultant: SupportGetAttribute):
    res_option = eval_expr(node, consultant, False, True)
    value = res_option.value
    if isinstance(value, TypeType):
        res_option.value = value.get_default_ins()
    return res_option


class PrepTypeEvalResult:
    def __init__(self, option_ins: Option[TypeIns], generic: bool) -> None:
        self.option_ins = option_ins
        self.generic = generic


class PrepTypeEvaluator(ExprParser):
    def __init__(
        self, consultant: SupportGetAttribute, annotation: bool, shallow: bool
    ) -> None:
        super().__init__(consultant, False, annotation)
        self.shallow = shallow
        self.generic = False

    def accept(self, node: ast.AST):
        res_option = super().accept(node)
        return PrepTypeEvalResult(res_option, self.generic)

    def visit_Subscript(self, node: ast.Subscript) -> TypeIns:
        self.generic = True
        if self.shallow:
            with self.block_container():
                left_ins = self.visit(node.value)
                assert isinstance(left_ins, TypeIns)
            return left_ins
        else:
            return super().visit_Subscript(node)
