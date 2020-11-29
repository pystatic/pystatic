import ast
from pystatic.typesys import TypeIns
from pystatic.exprparse import ExprParser, SupportGetAttribute


def eval_preptype(node: ast.AST, consultant: SupportGetAttribute,
                  annotation: bool, shallow: bool):
    return PrepTypeEvaluator(consultant, annotation, shallow).accept(node)


class PrepTypeEvalResult:
    def __init__(self, typeins: TypeIns, generic: bool) -> None:
        self.typeins = typeins
        self.generic = generic


class PrepTypeEvaluator(ExprParser):
    def __init__(self, consultant: SupportGetAttribute, annotation: bool,
                 shallow: bool) -> None:
        super().__init__(consultant, False, annotation)
        self.shallow = shallow
        self.generic = False

    def accept(self, node: ast.AST):
        res = self.visit(node)
        assert isinstance(res, TypeIns)
        return PrepTypeEvalResult(res, self.generic)

    def visit_Subscript(self, node: ast.Subscript) -> TypeIns:
        self.generic = True
        if self.shallow:
            with self.block_container():
                left_ins = self.visit(node.value)
                assert isinstance(left_ins, TypeIns)
            return left_ins
        else:
            return super().visit_Subscript(node)
