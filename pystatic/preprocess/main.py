import ast
from collections import deque
from typing import Optional, TYPE_CHECKING, Deque, List, Dict, Union
from pystatic.typesys import TypeModuleTemp
from pystatic.modfinder import ModuleFinder
from pystatic import preprocess
from pystatic.predefined import get_init_symtable
from pystatic.preprocess.definition import get_definition
from pystatic.preprocess.impt import resolve_import_type
from pystatic.preprocess.cls import resolve_cls_def
from pystatic.preprocess.typeins import resolve_local_typeins
from pystatic.target import Target, Stage
from pystatic.modfinder import ModuleFinder, ModuleFindRes

if TYPE_CHECKING:
    from pystatic.manager import Manager
    from pystatic.uri import Uri


class ReadNsAst(Exception):
    pass


def path2ast(path: str) -> ast.AST:
    """May throw FileNotFoundError or SyntaxError"""
    with open(path, 'r') as f:
        content = f.read()
        return ast.parse(content, type_comments=True)


class Preprocessor:
    def __init__(self, manager: 'Manager', finder: 'ModuleFinder') -> None:
        self.manager = manager  # TODO: is this necessary?
        self.finder = finder
        self.q_parse: Deque[Target] = deque()
        self.q_sym: Deque[Target] = deque()
        self.targets: Dict[Uri, Target] = {}

    def process(self, targets: Union[Target, List[Target]]):
        if isinstance(targets, Target):
            self.add_target(targets)
        elif isinstance(targets, list):
            for target in targets:
                assert isinstance(target, Target)
                self.add_target(target)

        self.deal_preparse()

    def get_module_temp(self, uri: 'Uri') -> Optional[TypeModuleTemp]:
        if uri in self.targets:
            return self.targets[uri].module_temp

    def add_target_uri(self, uri: 'Uri'):
        """Add target through its uri"""
        if uri not in self.targets:
            new_target = Target(uri, get_init_symtable())
            self.targets[uri] = new_target
            self.q_parse.append(new_target)

    def add_target(self, target: 'Target'):
        """Add target"""
        uri = target.uri
        if uri not in self.targets:
            self.targets[uri] = target
            assert target.stage == Stage.PreParse
            self.q_parse.append(target)

    def deal_preparse(self):
        to_check: List[Target] = []
        while len(self.q_parse) > 0:
            current = self.q_parse[0]
            self.q_parse.popleft()
            self.assert_parse(current)
            assert current.stage == Stage.PreSymtable
            assert current.ast
            to_check.append(current)
            self.q_sym.append(current)

            get_definition(current.ast, self, current.symtable,
                           self.manager.mbox, current.uri)

        for target in to_check:
            resolve_import_type(target.symtable, self)

        resolve_cls_def(to_check)

        for target in to_check:
            resolve_local_typeins(target.symtable)

    def uri2ast(self, uri: 'Uri') -> ast.AST:
        """Return the ast tree corresponding to uri.

        May throw SyntaxError or FileNotFoundError or ReadNsAst exception.
        """
        find_res = self.finder.find(uri)
        if not find_res:
            raise FileNotFoundError
        if find_res.res_type == ModuleFindRes.Module:
            assert len(find_res.paths) == 1
            assert find_res.target_file
            return path2ast(find_res.target_file)
        elif find_res.res_type == ModuleFindRes.Package:
            assert len(find_res.paths) == 1
            assert find_res.target_file
            return path2ast(find_res.target_file)
        elif find_res.res_type == ModuleFindRes.Namespace:
            raise ReadNsAst()
        else:
            assert False

    def parse(self, target: Target) -> ast.AST:
        # TODO: error handling
        assert target.stage == Stage.PreParse
        target.ast = self.uri2ast(target.uri)
        target.stage = Stage.PreSymtable
        return target.ast

    def assert_parse(self, target: Target):
        if target.stage <= Stage.PreParse:
            self.parse(target)

    def is_valid_uri(self, uri: 'Uri') -> bool:
        find_res = self.finder.find(uri)
        if find_res:
            return True
        else:
            return False
