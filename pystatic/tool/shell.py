import ast
from pystatic.error.errorbox import ErrorBox
from pystatic.target import Stage, Target
from pystatic.symtable import SymTable
from pystatic.manager import Manager
from pystatic.config import Config
from pystatic.symid import SymId
from pystatic.predefined import *

DEFAULT_INDENT = 4


class BlockSplitor:
    def __init__(self) -> None:
        self.level = 0
        self.buffer = []
        self.ps = "... "

    def remove_linebreak(self, line: str):
        i = len(line) - 1
        while i >= 0 and line[i] == "\n":
            i -= 1
        return line[: i + 1]

    def count_level(self, line: str):
        i = 0
        white_cnt = 0
        length = len(line)
        while i < length:
            if line[i] == "\t":
                white_cnt += DEFAULT_INDENT
            elif line[i] == " ":
                white_cnt += 1
            else:
                break
            i += 1

        if i == length:
            return 0
        return white_cnt // DEFAULT_INDENT

    def feed(self, line: str) -> bool:
        line = self.remove_linebreak(line)

        if not line:
            pass

        cur_level = self.count_level(line)
        self.level = min(self.level, cur_level)

        self.buffer.append(line)

        if line.endswith(":"):
            self.level += 1

        if self.level == 0:
            return True

        return False

    def get_str(self):
        return "\n".join(self.buffer)

    def clear(self):
        self.buffer = []
        self.level = 0

    def read(self) -> str:
        if self.feed(input()):
            res = self.get_str()
            self.clear()
            return res

        print(self.ps, end="")
        while not self.feed(input()):
            print(self.ps, end="")

        res = self.get_str()
        self.clear()
        return res


class Shell:
    def __init__(self, config: Config) -> None:
        self.manager = Manager(config)
        self.cwd = config.cwd
        self.splitor = BlockSplitor()
        self.ps = ">>> "

        self.symid = "__shell__"
        self.symtable = SymTable(
            self.symid, None, None, builtins_symtable, self.manager, TableScope.GLOB
        )
        self.symtable.glob = self.symtable
        self.errbox = ErrorBox(self.symid)
        self.target = Target(
            self.symid, self.symtable, self.errbox, "", False, Stage.FINISH
        )
        self.manager.add_check_target(self.target)

    def run(self):
        while True:
            print(self.ps, end="")
            blk_str = self.splitor.read()
            if not blk_str:
                continue

            if blk_str[0] == ":":
                blk_str = blk_str[1:]
                if blk_str == "quit":
                    break

            else:
                try:
                    astnode = ast.parse(blk_str, mode="eval")
                    # input is an expression
                    ins = self.manager.infer_expr(self.symid, blk_str)
                    if ins:
                        print(f"{ins}")
                    else:
                        print("Expression error")

                except SyntaxError:
                    try:
                        astnode = ast.parse(blk_str, type_comments=True)
                        if len(astnode.body) == 0:
                            continue
                        self.target.ast = astnode.body[0]
                        self.manager.recheck(self.symid, False)
                        self.manager.preprocess()

                        for err in self.errbox.error:
                            print(err)

                        self.errbox.clear()

                    except SyntaxError as e:
                        print(e)


def run(config: "Config", modules: List['SymId']):
    sh = Shell(config)
    sh.run()
