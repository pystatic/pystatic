import ast
import logging
from pystatic.module_finder import uri_from_impitem
from typing import Optional, TYPE_CHECKING, Union, Any, Dict
from collections import OrderedDict
from pystatic.util import BaseVisitor, ParseException, uri_parent, uri_last
from pystatic.env import Environment
from pystatic.reachability import Reach, infer_reachability_if
from pystatic.typesys import (TypeClassTemp, TypeModuleTemp, TypePackageTemp,
                              any_type, TypeVar, TypeType)
from pystatic.preprocess.annotation import (parse_comment_annotation,
                                            parse_annotation)
from pystatic.preprocess.cls import analyse_cls_def
from pystatic.preprocess.special_type import (special_typing_kind, SType,
                                              analyse_special_typing,
                                              get_typevar_name,
                                              analyse_typevar)
from pystatic.preprocess.func import parse_func

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from pystatic.manager import Manager


def collect_type_def(ast_root: ast.AST, env: Environment, manager: 'Manager'):
    """Collect types that defined in the module.

    Here type means names that can be used in annotation, like Class, TypeVar,
    TypeAlias...

    Node's reach attribute will also be modified.
    """
    return TypeDefCollector(env, manager).accept(ast_root)


def import_type_def(ast_root: ast.AST, env: Environment, manager: 'Manager'):
    """Import types in other modules into current module's type scope"""
    ImportResolver(env, manager).accept(ast_root)


def bind_type_name(ast_root: ast.AST, env: Environment):
    """Bind variable's name and type and gather type information"""
    return TypeBinder(env).accept(ast_root)


class TypeDefCollector(BaseVisitor):
    def __init__(self, env: Environment, manager: 'Manager'):
        super().__init__()
        self.env = env
        self.manager = manager

        self.reach_block = (Reach.NEVER, )

    def visit_If(self, node: ast.If):
        if_res = infer_reachability_if(node.test, self.manager.config)
        if if_res in (Reach.ALWAYS_TRUE, Reach.TYPE_TRUE):
            logging.debug(
                f'{self.env.module.uri}: line {node.lineno} is always true')
            for subif in node.orelse:
                setattr(subif, 'reach', Reach.NEVER)
            for stmt in node.body:
                self.visit(stmt)
        elif if_res in (Reach.ALWAYS_FALSE, Reach.TYPE_FALSE):
            for stmt in node.body:
                setattr(stmt, 'reach', Reach.NEVER)
            for subif in node.orelse:
                self.visit(subif)
        else:
            for stmt in node.body:
                self.visit(stmt)
            for subif in node.orelse:
                self.visit(subif)

    def visit_ClassDef(self, node: ast.ClassDef):
        if not self.env.lookup_local_type(node.name):
            cls_uri = self.env.current_uri + f'.{node.name}'
            tp = TypeClassTemp(cls_uri)
            self.env.add_type(node.name, tp)
            logger.debug(f'add class {cls_uri}')

            # try to get nested classes
            self.env.enter_class(node.name)
            for sub_node in node.body:
                self.visit(sub_node)
            self.env.pop_scope()
        else:
            self.env.add_err(node, f'{node.name} already defined')
            setattr(node, 'reach', Reach.CLS_REDEF)

    def visit_Assign(self, node: ast.Assign):
        spec = special_typing_kind(node)
        if spec == SType.TypeVar:
            try:
                assert isinstance(node.value, ast.Call)
                tpvar_name = get_typevar_name(node.value)
                new_typevar = TypeVar(tpvar_name)
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if not self.env.lookup_local_type(target.id):
                            self.env.add_type(target.id, new_typevar)
                            logger.debug(f'Add TypeVar {target.id}')
            except ParseException as e:
                self.env.add_err(e.node, e.msg or f'invalid syntax')

    def visit_AnnAssign(self, node: ast.AnnAssign):
        spec = special_typing_kind(node)
        if spec == SType.TypeVar:
            new_typevar = TypeVar('')
            target = node.target
            if isinstance(target, ast.Name):
                if not self.env.lookup_local_type(target.id):
                    self.env.add_type(target.id, new_typevar)
                    logger.debug(f'Add TypeVar {target.id}')

    # don't visit types defined inside a function
    def visit_FunctionDef(self, node):
        pass


class ImportResolver(BaseVisitor):
    def __init__(self, env: 'Environment', manager: 'Manager'):
        super().__init__()
        self.env = env
        self.manager = manager

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            # NOTE: alias.name must be an absolute uri? I'm not sure about it
            # NOTE: if not, please let me know
            parent_uri = uri_parent(alias.name)
            last_uri = uri_last(alias.name)

            res_type: Any
            if parent_uri:
                parent_type = self.manager.deal_import(parent_uri)
                if isinstance(parent_type, TypePackageTemp):
                    res_type = self.manager.deal_import(alias.name)
                elif isinstance(parent_type, TypeModuleTemp):
                    res_type = parent_type.getattr(last_uri)
                else:
                    res_type = None
            else:
                res_type = self.manager.deal_import(alias.name)
            if isinstance(res_type, TypeModuleTemp) or isinstance(
                    res_type, TypeType):
                if isinstance(res_type, TypeType):
                    res_type = res_type.temp
                name = alias.asname if alias.asname else alias.name
                self.env.add_type(name, res_type)
                logger.debug(
                    f'Add {res_type.name} to {self.env.module.name} as {name}')
            else:
                self.env.add_err(node, f'{alias.name} not found')

    def visit_ImportFrom(self, node: ast.ImportFrom):
        imp_name = node.module if node.module else ''
        imp_name = '.' * node.level + imp_name
        # get absolute uri
        imp_name = uri_from_impitem(imp_name, self.env.module)

        parent_type = self.manager.deal_import(imp_name)
        res_type: Any

        if parent_type is None:
            self.env.add_err(node, f'module {imp_name} not found')
        elif isinstance(parent_type, TypePackageTemp) or isinstance(
                parent_type, TypeModuleTemp):
            for alias in node.names:
                if isinstance(parent_type, TypePackageTemp):
                    res_name = imp_name + '.' + alias.name
                    res_type = self.manager.deal_import(res_name)
                elif isinstance(parent_type, TypeModuleTemp):
                    res_type = parent_type.getattr(alias.name)
                else:
                    res_type = None
                if isinstance(res_type, TypeModuleTemp) or isinstance(
                        res_type, TypeType):
                    if isinstance(res_type, TypeType):
                        res_type = res_type.temp
                    name = alias.asname if alias.asname else alias.name
                    self.env.add_type(name, res_type)
                    logger.debug(
                        f'Add {res_type.name} to {self.env.module.name} as {name}'
                    )
                else:
                    self.env.add_err(node,
                                     f'{imp_name}.{alias.name} not found')
        else:
            self.env.add_err(node, f'{imp_name} is not a module')

    # don't visit import statement inside a function or class definition
    def visit_ClassDef(self, node: ast.ClassDef):
        tp_temp = self.env.lookup_local_type(node.name)
        assert isinstance(tp_temp, TypeClassTemp)
        base_list, var_list = analyse_cls_def(node, self.env)
        for base_tp in base_list:
            tp_temp.add_base(base_tp)
            logger.debug(f'Add base class {base_tp.name} to {tp_temp.name}')
        tp_temp.set_typelist(var_list)

        self.env.add_type(node.name, tp_temp)

    def visit_FunctionDef(self, node):
        pass


class TypeBinder(BaseVisitor):
    """Bind name to their type according to the type annotation"""
    def __init__(self, env: Environment):
        super().__init__()
        self.env = env

    def accept(self, node: ast.AST):
        self.visit(node)

    def visit_Assign(self, node: ast.Assign):
        res = _def_visitAssign(self.env, node)
        for name, target_type in res.items():
            self.env.add_var(name, target_type)
            logger.debug(
                f'Add {self.env.current_uri}.{name}, type: {target_type}')

    def visit_AnnAssign(self, node: ast.AnnAssign):
        res = _def_visitAnnAssign(self.env, node)
        for name, target_type in res.items():
            self.env.add_var(name, target_type)
            logger.debug(
                f'Add {self.env.current_uri}.{name}, type: {target_type}')

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if self.env.lookup_local_var(node.name):
            self.env.add_err(node, f'{node.name} already defined')
            return
        else:
            func_type = parse_func(node, self.env)
            if func_type:
                self.env.add_var(node.name, func_type)
                logger.debug(f'Add function {node.name}: {func_type}')

    def visit_ClassDef(self, node: ast.ClassDef):
        if not self.env.lookup_local_var(node.name):
            ClassDefVisitor(self.env).accept(node)

            # add class var to local scope
            cls_tp = self.env.lookup_local_type(node.name)
            assert isinstance(
                cls_tp,
                TypeClassTemp), f"{cls_tp} should be collected and is a class"
            self.env.add_var(node.name, cls_tp.get_default_type())

            logging.debug(f'finish visit class {cls_tp.name}')
        else:
            self.env.add_err(node, f'{node.name} already defined')


class ClassDefVisitor(TypeBinder):
    """Visit a class definition and add members to the class type"""
    def __init__(self, env: Environment):
        super().__init__(env)

    def accept(self, node: ast.AST):
        assert isinstance(node, ast.ClassDef)
        if not self.env.lookup_local_var(node.name):
            tp = self.env.enter_class(node.name)
            if tp:
                # TODO: bases
                self.tp = tp
                for sub_node in node.body:
                    self.visit(sub_node)

                self.env.pop_scope()
            else:
                logger.warning(f"ClassDefVisitor doesn't catch {node.name}")
        else:
            self.env.add_err(node, f'{node.name} redefined')

    def visit_FunctionDef(self, node: ast.FunctionDef):
        ClassFuncDefVisitor(self.env, self.tp).accept(node)


class ClassFuncDefVisitor(BaseVisitor):
    """Visit methods defined in a class and add it to the class type.
    Also collect data members defined inside the class and add them to
    the class type"""
    def __init__(self, env: Environment, cls_temp: TypeClassTemp):
        super().__init__()
        self.env = env
        self.cls_temp = cls_temp

    def accept(self, node: ast.FunctionDef):
        if self.cls_temp.get_local_attr(node.name):
            # TODO: already defined error?
            return
        else:
            func_type = parse_func(node, self.env)
            if func_type:
                self.cls_temp.setattr(node.name, func_type)
                logger.debug(
                    f"Add class method: {self.cls_temp.name}.{node.name}, type: {func_type}"
                )
                self.visit(node)

    def is_cls_attr(self, node: ast.Attribute):
        if isinstance(node.value, ast.Name) and node.value.id == 'self':
            return node.attr
        return None

    def visit_Assign(self, node: ast.Assign):
        comment_type = parse_comment_annotation(node, self.env)
        comment_type = comment_type if comment_type else any_type
        for sub_node in node.targets:
            if isinstance(sub_node, ast.Attribute):
                attr = self.is_cls_attr(sub_node)
                if attr and not self.cls_temp.get_local_attr(attr):
                    self.cls_temp.setattr(attr, comment_type)
                    logger.debug(
                        f'Add class attribute: {self.cls_temp.name}.{attr}, type: {comment_type}'
                    )

    def visit_AnnAssign(self, node: ast.AnnAssign):
        ann_type = parse_annotation(node.annotation, self.env, False)
        ann_type = ann_type if ann_type else any_type
        if isinstance(node.target, ast.Attribute):
            attr = self.is_cls_attr(node.target)
            if attr and not self.cls_temp.get_local_attr(attr):
                self.cls_temp.setattr(attr, ann_type)
                logger.debug(
                    f'Add class attribute: {self.cls_temp.name}.{attr} type: {ann_type}'
                )


def _def_visitAssign(env: Environment,
                     node: ast.Assign) -> Dict[str, TypeType]:
    """Get the variables defined in an ast.Assign node"""
    new_var = OrderedDict()
    spec = special_typing_kind(node)
    if not spec:
        comment_type = parse_comment_annotation(node, env)
        comment_type = comment_type if comment_type else any_type  # default: Any
        for sub_node in reversed(node.targets):
            if isinstance(sub_node, ast.Name):
                if not env.lookup_local_var(
                        sub_node.id) and sub_node.id not in new_var:
                    # this assignment is also a definition
                    # TODO: warning here if redefine?
                    new_var[sub_node.id] = comment_type
    elif spec == SType.TypeVar:
        tpvar_temp = analyse_typevar(node, env)
        if tpvar_temp:
            new_var[tpvar_temp.basename] = tpvar_temp.get_default_type()
    else:
        assert 0, "Not implemented yet"
    return new_var


def _def_visitAnnAssign(env: Environment,
                        node: ast.AnnAssign) -> Dict[str, TypeType]:
    """Get the variables defined in an ast.AnnAssign node"""
    # TODO: refactor this
    new_var = OrderedDict()
    spec = special_typing_kind(node)
    if not spec:
        ann_type = parse_annotation(node.annotation, env, False)
        ann_type = ann_type if ann_type else any_type
        if isinstance(node.target, ast.Name):
            if not env.lookup_local_var(node.target.id):
                # this assignment is also a definition
                new_var[node.target.id] = ann_type
    elif spec == SType.TypeVar:
        tpvar_temp = analyse_typevar(node, env)
        if tpvar_temp:
            new_var[tpvar_temp.basename] = tpvar_temp.get_default_type()
    else:
        assert 0, "Not implemented yet"
    return new_var
