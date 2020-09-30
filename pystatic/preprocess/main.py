import ast
from collections import deque
from typing import Optional, TYPE_CHECKING, Deque, List, Dict
from pystatic.typesys import TypeModuleTemp
from pystatic.modfinder import ModuleFinder
from pystatic.predefined import get_init_symtable
from pystatic.preprocess.definition import get_definition, get_definition_in_method
from pystatic.preprocess.impt import resolve_import_type
from pystatic.preprocess.cls import resolve_cls_def, resolve_cls_method, resolve_cls_attr
from pystatic.preprocess.local import resolve_local_typeins
from pystatic.target import BlockTarget, MethodTarget, Target, Stage
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

        self.q_parse: Deque[BlockTarget] = deque()

        self.targets: Dict[Uri, Target] = {}

    def process_block(self, blocks: List[BlockTarget], added: bool = False):
        """Process a block level target.

        :param added: whether these blocks are added to the q_parse before
        (default: False)
        """
        if not added:
            for block in blocks:
                self.q_parse.append(block)
        self._deal()

    def process_module(self, targets: List[Target]):
        fresh_targets = []
        for target in targets:
            assert isinstance(target, Target)
            if self.add_cache_target(target):
                # this is a new target
                fresh_targets.append(target)

        self.process_block(fresh_targets, True)  # type: ignore

    def get_module_temp(self, uri: 'Uri') -> Optional[TypeModuleTemp]:
        if uri in self.targets:
            return self.targets[uri].module_temp

    def add_cache_target_uri(self, uri: 'Uri'):
        """Add and cache target through its uri"""
        if uri not in self.targets:
            new_target = Target(uri, get_init_symtable())
            self.targets[uri] = new_target
            self.q_parse.append(new_target)
            return True
        return False

    def add_cache_target(self, target: 'Target'):
        """Add and cache target"""
        assert isinstance(target, Target)
        uri = target.uri
        if uri not in self.targets:
            assert target.stage == Stage.PreParse
            self.targets[uri] = target
            self.q_parse.append(target)
            return True
        return False

    def _deal(self):
        to_check: List[BlockTarget] = []
        while len(self.q_parse) > 0:
            current = self.q_parse[0]
            self.q_parse.popleft()
            self.assert_parse(current)
            assert current.stage == Stage.PreSymtable
            assert current.ast
            to_check.append(current)

            # get current module's class definitions
            if isinstance(current, MethodTarget):
                get_definition_in_method(current, self, self.manager.mbox)
            else:
                get_definition(current, self, self.manager.mbox)

        # get type imported from other module
        for target in to_check:
            resolve_import_type(target.symtable, self)

        resolve_cls_def(to_check)

        # from now on, all valid types in the module should be correctly
        # identified because possible type(class) information is collected
        for target in to_check:
            resolve_local_typeins(target.symtable)

        for target in to_check:
            resolve_cls_method(target.symtable, target.uri, self)
            resolve_cls_attr(target.symtable)

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

    def parse(self, target: BlockTarget) -> ast.AST:
        # TODO: error handling
        assert target.stage == Stage.PreParse
        target.ast = self.uri2ast(target.uri)
        return target.ast

    def assert_parse(self, target: BlockTarget):
        if target.stage <= Stage.PreParse:
            if isinstance(target, Target):
                self.parse(target)
            else:
                assert target.ast
        target.stage = Stage.PreSymtable

    def is_valid_uri(self, uri: 'Uri') -> bool:
        find_res = self.finder.find(uri)
        if find_res:
            return True
        else:
            return False
