import ast
from pystatic.typesys import TypeIns, TypeType
from pystatic.result import Result
from pystatic.infer.infer_expr import ExprInferer, SupportGetAttribute, infer_expr


def eval_preptype(
    node: ast.AST, consultant: SupportGetAttribute, annotation: bool, shallow: bool
):
    return PrepTypeEvaluator(consultant, annotation, shallow).accept(node)


class PrepTypeEvalResult:
    def __init__(self, result: Result[TypeIns], generic: bool) -> None:
        self.result = result
        self.generic = generic


class PrepTypeEvaluator(ExprInferer):
    """Evaluate a node's type and can run in shallow mode.

    shallow mode: won't dive inside subscript node
    """

    def __init__(
        self, consultant: SupportGetAttribute, annotation: bool, shallow: bool
    ) -> None:
        super().__init__(consultant, annotation)
        self.shallow = shallow
        self.generic = False

    def accept(self, node: ast.AST):
        result = super().accept(node)
        return PrepTypeEvalResult(result, self.generic)

    def visit_Subscript(self, node: ast.Subscript) -> TypeIns:
        self.generic = True
        if self.shallow:
            with self.block_container():
                left_ins = self.visit(node.value)
                assert isinstance(left_ins, TypeIns)
            return left_ins
        else:
            return super().visit_Subscript(node)
