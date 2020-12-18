import ast


class Position:
    __slots__ = ["lineno", "end_lineno", "col_offset", "end_col_offset"]

    def __init__(
        self, lineno: int, end_lineno: int, col_offset: int, end_col_offset: int
    ):
        self.lineno = lineno
        self.end_lineno = end_lineno
        self.col_offset = col_offset
        self.end_col_offset = end_col_offset

    def __lt__(self, other: "Position"):
        return (self.lineno, self.col_offset, self.end_lineno, self.end_col_offset) < (
            other.lineno,
            other.col_offset,
            other.end_lineno,
            other.end_col_offset,
        )


def ast_to_position(node: ast.AST) -> Position:
    lineno = node.lineno
    end_lineno = node.end_lineno or lineno
    col_offset = node.col_offset
    end_col_offset = node.end_col_offset or col_offset
    return Position(lineno, end_lineno, col_offset, end_col_offset)
