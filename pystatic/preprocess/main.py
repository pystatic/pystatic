import ast
from collections import deque
from pystatic.uri import uri2list
from typing import Optional, TYPE_CHECKING, Deque, List, Dict
from pystatic.typesys import TypeModuleTemp, TypePackageTemp
from pystatic.modfinder import ModuleFinder
from pystatic.predefined import get_init_module_symtable
from pystatic.preprocess.definition import (get_definition,
                                            get_definition_in_method)
from pystatic.preprocess.impt import resolve_import_type, resolve_import_ins
from pystatic.preprocess.cls import (resolve_cls_def, resolve_cls_method,
                                     resolve_cls_attr)
from pystatic.preprocess.local import resolve_local_typeins, resolve_local_func
from pystatic.target import BlockTarget, MethodTarget, Target, Stage
from pystatic.modfinder import ModuleFinder, ModuleFindRes

if TYPE_CHECKING:
    from pystatic.message import MessageBox
    from pystatic.uri import Uri


class ReadNsAst(Exception):
    pass


def path2ast(path: str) -> ast.AST:
    """May throw FileNotFoundError or SyntaxError"""
    with open(path, 'r') as f:
        content = f.read()
        return ast.parse(content, type_comments=True)


class Preprocessor:
    def __init__(self, mbox: 'MessageBox', finder: 'ModuleFinder') -> None:
        self.mbox = mbox
        self.finder = finder

        # dequeue that store targets waiting for get definitions in them
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
            if target.stage < Stage.Processed:
                assert isinstance(target, Target)
                if self.add_cache_target(target):
                    # this is a new target
                    fresh_targets.append(target)

        self.process_block(fresh_targets, True)  # type: ignore

    def get_module_temp(self, uri: 'Uri') -> Optional[TypeModuleTemp]:
        if uri in self.targets:
            return self.targets[uri].module_temp

    def _add_cache_target_uri(self, uri: 'Uri'):
        if uri not in self.targets:
            new_target = Target(uri, get_init_module_symtable(uri))
            self.targets[uri] = new_target
            self.q_parse.append(new_target)
            return True
        return False

    def add_cache_target_uri(self, uri: 'Uri'):
        """Add and cache target through its uri"""
        urilist = uri2list(uri)
        assert urilist
        cur_uri = urilist[0]
        self._add_cache_target_uri(cur_uri)
        for i in range(1, len(urilist)):
            cur_uri += f'.{urilist[i]}'
            self._add_cache_target_uri(cur_uri)

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

            # get current module's class definitions.
            if isinstance(current, MethodTarget):
                get_definition_in_method(current, self, self.mbox)
            else:
                get_definition(current, self, self.mbox)

        # get type imported from other module.
        for target in to_check:
            resolve_import_type(target.symtable, self)

        resolve_cls_def(to_check, self.mbox)

        # from now on, all valid types in the module should be correctly
        # identified because possible type(class) information is collected.
        for target in to_check:
            resolve_local_typeins(target.symtable, self.mbox)
            resolve_local_func(target.symtable, self.mbox)

        for target in to_check:
            resolve_import_ins(target.symtable, self)

        for target in to_check:
            resolve_cls_method(target.symtable, target.uri, self, self.mbox)
            resolve_cls_attr(target.symtable, self.mbox)

            if isinstance(target, Target):
                target.stage = Stage.Processed

    def parse_target(self, target: Target):
        # TODO: error handling
        assert target.stage == Stage.PreParse
        find_res = self.finder.find(target.uri)

        if not find_res:
            raise FileNotFoundError

        if find_res.res_type == ModuleFindRes.Module:
            assert len(find_res.paths) == 1
            assert find_res.target_file
            target.ast = path2ast(find_res.target_file)

        elif find_res.res_type == ModuleFindRes.Package:
            assert len(find_res.paths) == 1
            assert find_res.target_file
            target.ast = path2ast(find_res.target_file)
            target.module_temp = TypePackageTemp(find_res.paths,
                                                 target.symtable, target.uri)

        elif find_res.res_type == ModuleFindRes.Namespace:
            raise ReadNsAst()

        else:
            assert False

    def assert_parse(self, target: BlockTarget):
        if target.stage <= Stage.PreParse:
            if isinstance(target, Target):
                self.parse_target(target)
            else:
                assert target.ast
        target.stage = Stage.PreSymtable

    def is_valid_uri(self, uri: 'Uri') -> bool:
        find_res = self.finder.find(uri)
        if find_res:
            return True
        else:
            return False
