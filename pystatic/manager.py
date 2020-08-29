import os
import ast
import logging
import enum
from typing import Optional, List, TextIO, Set, Dict
from pystatic.typesys import TypeModuleTemp, TypePackageTemp
from pystatic.config import Config
from pystatic.env import get_init_env
from pystatic.preprocess.preprocess import (collect_type_def, import_type_def,
                                            bind_type_name)
from pystatic.module_finder import (ModuleFinder, ModuleFindRes)
from pystatic.env import Environment
from pystatic.util import Uri

logger = logging.getLogger(__name__)


class ReadNsAst(Exception):
    """Try to read a namespace package's ast(which has no __init__.py)"""
    pass


class AnalysisStage(enum.IntEnum):
    """AnalysisStage

    Number ascends as the analysis going deeper
    """
    UnTouched = 0
    Collected = 1
    Imported = 2
    Binded = 3
    Checked = 4


class AnalysisTarget:
    def __init__(self,
                 uri: Uri,
                 ast_rt: Optional[ast.AST] = None,
                 module: Optional[TypeModuleTemp] = None,
                 stage: AnalysisStage = AnalysisStage.UnTouched):
        self.uri = uri
        self.ast_rt = ast_rt

        self.module: TypeModuleTemp
        self.module = module or TypeModuleTemp(uri, {}, {})

        self.stage: AnalysisStage
        self.stage = stage or AnalysisStage.UnTouched

        self.env = get_init_env(self.module)

    def __hash__(self):
        return hash(self.uri)


class Manager:
    def __init__(self, config, module_files: List[str],
                 package_files: List[str], stdout: TextIO, stderr: TextIO):
        # Modules that need to check
        self.check_targets: Set[AnalysisTarget] = set()

        self.config = Config(config)

        self.user_path: Set[str] = set()
        self.set_user_path(module_files)
        self.set_user_path(package_files)
        self.finder = ModuleFinder(self.config.manual_path,
                                   list(self.user_path), self.config.sitepkg,
                                   self.config.typeshed)

        # Modules that need to be analysed
        # Not all modules need to go on to the check stage
        self.targets: Dict[Uri, AnalysisTarget] = {}

        self.stdout = stdout
        self.stderr = stderr

        self.generate_targets(module_files)
        self.generate_targets(package_files)

    def start_check(self):
        # now the scheme is simple, but it's temporary
        # later may use some scheme to resolve circular import
        for target in self.check_targets:
            try:
                self.collect_target_type(target)
            except FileNotFoundError:
                logger.warning(f'{target.uri} not found')
            except SyntaxError:
                logger.warning(f'{target.uri} has syntax error')

        for target in self.check_targets:
            self.preprocess_target(target)

        # for debug purpose, will be removed in the future
        for target in self.targets.values():
            for err in target.env.err:
                print(err)

    def set_user_path(self, srcfiles: List[str]):
        """Set user path according to sources"""
        for srcfile in srcfiles:
            srcfile = os.path.realpath(srcfile)
            if not os.path.exists(srcfile):
                logger.warning(f"{srcfile} doesn't exist")
                continue
            rt_path = crawl_path(os.path.dirname(srcfile))
            if rt_path not in self.user_path:
                self.user_path.add(rt_path)
                logger.debug(f'Add user path: {rt_path}')

    def generate_targets(self, srcfiles: List[str]):
        """Generate AnalysisTarget according to the srcfiles"""
        for srcfile in srcfiles:
            srcfile = os.path.realpath(srcfile)
            if not os.path.exists(srcfile):
                # already warned in set_user_path
                continue
            rt_path = crawl_path(os.path.dirname(srcfile))
            uri = generate_uri(rt_path, srcfile)
            target = AnalysisTarget(uri)
            if target not in self.check_targets:
                try:
                    self.collect_target_type(target)
                    self.check_targets.add(target)
                    self.register(target)
                except FileNotFoundError:
                    # TODO: add to err handler?
                    logger.warning(f'{srcfile} not found')
                except SyntaxError:
                    # TODO: add to err handler?
                    logger.warning(f'{uri} has syntax error')

    def deal_import(self, uri: Uri) -> Optional[TypeModuleTemp]:
        """uri must be absolute"""
        if not uri:
            logger.warning(f'Module {uri} not found')
            return None

        # cached result
        if uri in self.targets and self.targets[
                uri].stage >= AnalysisStage.Collected:
            return self.targets[uri].module

        find_res = self.finder.find(uri)
        if find_res:
            if find_res.res_type == ModuleFindRes.Module:
                target = AnalysisTarget(uri)
                try:
                    # self.collect_target_type(target)
                    self.preprocess_target(target)
                    self.register(target)
                except (SyntaxError, FileNotFoundError):
                    return None
                else:
                    return target.module

            elif find_res.res_type == ModuleFindRes.Package:
                # TODO: analyse the __init__.py file under the package
                pkg = TypePackageTemp(find_res.paths, uri, {}, {})
                target = AnalysisTarget(uri, None, pkg, AnalysisStage.Checked)
                self.register(target)
                return pkg

            elif find_res.res_type == ModuleFindRes.Namespace:
                ns_pkg = TypePackageTemp(find_res.paths, uri, {}, {})
                target = AnalysisTarget(uri, None, ns_pkg,
                                        AnalysisStage.Checked)
                self.register(target)
                return ns_pkg

        return None

    def register(self, target: AnalysisTarget):
        if target.uri not in self.targets:
            self.targets[target.uri] = target

    def collect_target_type(self, target: AnalysisTarget):
        """Collect type information in the target's module

        May throw SyntaxError or FileNotFoundError exception
        """
        if target.stage < AnalysisStage.Collected:
            if not target.ast_rt:
                try:
                    target.ast_rt = self.uri2ast(target.uri)
                    collect_type_def(target.ast_rt, target.env, self)
                    glob = target.env.glob_scope
                    target.module = TypeModuleTemp(target.uri, glob.types,
                                                   glob.local)

                    target.stage = AnalysisStage.Collected
                except ReadNsAst:
                    target.ast_rt = None
                    target.stage = AnalysisStage.Checked

    def preprocess_target(self, target: AnalysisTarget):
        """Preprocess a target

        This function will set the target's stage at the same time
        """
        try:
            self.collect_target_type(target)
        except (SyntaxError, FileNotFoundError):
            logger.warning(f'Failed to parse {target.uri}')
            return None

        assert target.ast_rt
        if target.stage < AnalysisStage.Imported:
            import_type_def(target.ast_rt, target.env, self)
            target.stage = AnalysisStage.Imported
        if target.stage < AnalysisStage.Binded:
            bind_type_name(target.ast_rt, target.env)
            target.stage = AnalysisStage.Binded

    def preprocess_subscope(self, ast_rt: ast.AST, env: Environment):
        """Preprocess a subscope(ususally inside a function)

        This function will modify env and store results in it
        """
        collect_type_def(ast_rt, env, self)
        import_type_def(ast_rt, env, self)
        bind_type_name(ast_rt, env)

    def uri2ast(self, uri: Uri) -> ast.AST:
        """Return the ast tree corresponding to uri.

        May throw SyntaxError or FileNotFoundError or ReadNsAst exception.
        """
        find_res = self.finder.find(uri)
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


def path2ast(path: str) -> ast.AST:
    """May throw FileNotFoundError or SyntaxError"""
    with open(path, 'r') as f:
        content = f.read()
        return ast.parse(content, type_comments=True)


def crawl_path(path: str) -> str:
    """Move up the directory until find a directory that doesn't contains __init__.py.

    This may fail when analysing a namespace package.
    """
    while True:
        init_file = os.path.join(path, '__init__.py')
        if os.path.isfile(init_file):
            dirpath = os.path.dirname(path)
            if path == dirpath:
                # TODO: warning here
                break
            else:
                path = dirpath
        else:
            break
    return path


def generate_uri(prefix_path: str, src_path: str) -> Uri:
    """Generate uri from the path

    Example:
        If prefix_path is '/a/b/c' and src_path is /a/b/c/d/e.py
        then return 'd.e'
    """
    commonpath = os.path.commonpath([prefix_path, src_path])
    relpath = os.path.relpath(src_path, commonpath)
    if relpath.endswith('.py'):
        relpath = relpath[:-3]
    elif relpath.endswith('.pyi'):
        relpath = relpath[:-4]
    return '.'.join(relpath.split(os.path.sep))
