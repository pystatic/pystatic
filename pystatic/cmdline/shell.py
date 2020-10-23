import ast
from pystatic.symtable import SymTable
from pystatic.manager import Manager
from pystatic.config import Config
from pystatic.predefined import get_init_module_symtable

DEFAULT_INDENT = 4


class BlockSplitor:
    def __init__(self) -> None:
        self.level = 0
        self.buffer = []
        self.ps = '... '

    def remove_linebreak(self, line: str):
        i = len(line) - 1
        while i >= 0 and line[i] == '\n':
            i -= 1
        return line[:i + 1]

    def count_level(self, line: str):
        i = 0
        white_cnt = 0
        length = len(line)
        while i < length:
            if line[i] == '\t':
                white_cnt += DEFAULT_INDENT
            elif line[i] == ' ':
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

        if line.endswith(':'):
            self.level += 1

        if self.level == 0:
            return True

        return False

    def get_str(self):
        return '\n'.join(self.buffer)

    def clear(self):
        self.buffer = []
        self.level = 0

    def read(self) -> str:
        if self.feed(input()):
            res = self.get_str()
            self.clear()
            return res

        print(self.ps, end='')
        while not self.feed(input()):
            print(self.ps, end='')

        res = self.get_str()
        self.clear()
        return res


class Shell:
    def __init__(self, config: Config) -> None:
        self.manager = Manager(config)
        self.cwd = config.cwd
        self.splitor = BlockSplitor()
        self.ps = '>>> '

        self.symtable = get_init_module_symtable('__shell__')

    def run(self):
        while True:
            print(self.ps, end='')
            blk_str = self.splitor.read()
            if not blk_str:
                continue

            if blk_str[0] == ':':
                blk_str = blk_str[1:]
                if blk_str == 'quit':
                    break

            else:
                try:
                    astnode = ast.parse(blk_str)
                    if len(astnode.body) == 0:
                        continue
                    astnode = astnode.body[0]

                except SyntaxError as e:
                    print(e)


def run_shell(config: 'Config'):
    sh = Shell(config)
