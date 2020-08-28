import ast
import logging
from typing import TYPE_CHECKING
from collections import OrderedDict
from pystatic.util import BaseVisitor
from pystatic.env import Environment
from pystatic.reachability import Reach, infer_reachability_if
from pystatic.typesys import TypeClassTemp, any_type, TypeVar
from pystatic.preprocess.annotation import (parse_comment_annotation,
                                            parse_annotation, get_cls_typevars)
from pystatic.preprocess.typing import is_special_typing, SType
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
    return ImportResolver(env, manager).accept(ast_root)


def generate_type_binding(ast_root: ast.AST, env: Environment):
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

            var_lst, base_lst = get_cls_typevars(node, self.env)
            tpvar_dict = OrderedDict()
            for tpvar_name in var_lst:
                tpvar = self.env.lookup_type(tpvar_name)
                assert isinstance(tpvar, TypeVar)
                tpvar_dict[tpvar_name] = tpvar
            tp.set_typevar(tpvar_dict)
            for base_tp in base_lst:
                tp.add_base(base_tp.name, base_tp)
                logger.debug(f'Add base class {base_tp.name} to {cls_uri}')

            self.env.add_type(node.name, tp)

            logger.debug(f'Add class {cls_uri}(' + ', '.join(var_lst) + ')')

            # try to get nested classes
            self.env.enter_class(node.name)
            for sub_node in node.body:
                self.visit(sub_node)
            self.env.pop_scope()

        else:
            self.env.add_err(node, f'{node.name} already defined')
            setattr(node, 'reach', Reach.CLS_REDEF)

    def visit_Assign(self, node: ast.Assign):
        spec = is_special_typing(node)
        if spec == SType.TypeVar:
            new_typevar = TypeVar('')
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if not self.env.lookup_local_type(target.id):
                        self.env.add_type(target.id, new_typevar)
                        logger.debug(f'Add TypeVar {target.id}')

    def visit_AnnAssign(self, node: ast.AnnAssign):
        spec = is_special_typing(node)
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
            m_type = self.manager.deal_module_import(alias.name,
                                                     self.env.module)
            if m_type is None:
                self.env.add_err(node, f'module {alias.name} not found')
            else:
                name = alias.asname if alias.asname else alias.name
                self.env.add_type(name, m_type)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        imp_name = node.module if node.module else ''
        imp_name = '.' * node.level + imp_name
        m_type = self.manager.deal_module_import(imp_name, self.env.module)
        if m_type is None:
            self.env.add_err(node, f'module {imp_name} not found')
        else:
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name
                if isinstance(m_type, TypeClassTemp):
                    res = m_type.get_type(alias.name)
                    if res is None:
                        self.env.add_err(node,
                                         f'{imp_name}.{alias.name} not found')
                    else:
                        self.env.add_type(name, res)
                else:
                    self.env.add_err(node,
                                     f'{imp_name}.{alias.name} not found')

    # don't visit import statement inside a function or class definition
    def visit_ClassDef(self, node):
        pass

    def visit_FunctionDef(self, node):
        pass


class ClassFuncDefVisitor(BaseVisitor):
    """Visit methods defined in a class and add it to the class type.
    Also collect data members defined inside the class and add them to
    the class type
    """
    def __init__(self, env: Environment, tp):
        super().__init__()
        self.env = env
        self.tp = tp

    def accept(self, node: ast.FunctionDef):
        if node.name in self.tp:
            return
        else:
            func_type = parse_func(node, self.env)
            if func_type:
                self.tp.add_attribute(node.name, func_type)
                logger.debug(
                    f"Add class method: {self.tp.name}.{node.name}, type: {func_type}"
                )
                self.visit(node)

    def is_cls_attr(self, node: ast.Attribute):
        if isinstance(node.value, ast.Name) and node.value.id == 'self':
            return node.attr
        return None

    def visit_Assign(self, node: ast.Assign):
        com_tp = parse_comment_annotation(node, self.env)
        assign_tp = com_tp if com_tp else any_type
        for sub_node in node.targets:
            if isinstance(sub_node, ast.Attribute):
                attr = self.is_cls_attr(sub_node)
                if attr and attr not in self.tp:
                    self.tp.add_attribute(attr, assign_tp)
                    logger.debug(
                        f'Add class attribute: {self.tp.name}.{attr}, type: {assign_tp}'
                    )

    def visit_AnnAssign(self, node: ast.AnnAssign):
        tp = parse_annotation(node.annotation, self.env)
        assign_tp = tp if tp else any_type
        if isinstance(node.target, ast.Attribute):
            attr = self.is_cls_attr(node.target)
            if attr and attr not in self.tp:
                self.tp.add_attribute(attr, assign_tp)
                logger.debug(
                    f'Add class attribute: {self.tp.name}.{attr} type: {assign_tp}'
                )


class ClassDefVisitor(BaseVisitor):
    """Visit a class definition and add members to the class type"""
    def __init__(self, env: Environment):
        super().__init__()
        self.env = env

    def accept(self, node: ast.ClassDef):
        if not self.env.lookup_local_var(node.name):
            tp = self.env.enter_class(node.name)
            if tp:
                # TODO: bases
                self.tp = tp
                for sub_node in node.body:
                    self.visit(sub_node)

                self.env.pop_scope()
            else:
                logger.warn(f"ClassDefVisitor doesn't catch {node.name}")
        else:
            self.env.add_err(node, f'{node.name} redefined')

    def visit_Assign(self, node: ast.Assign):
        if not is_special_typing(node):
            res = _def_visitAssign(self.env, node)
            for name, var_tp in res.items():
                self.env.add_var(name, var_tp)
                self.tp.add_attribute(name, var_tp)
                logger.debug(
                    f'Add class attribute: {self.env.current_uri}.{name}, type: {var_tp}'
                )

    def visit_AnnAssign(self, node: ast.AnnAssign):
        if not is_special_typing(node):
            name, var_tp = _def_visitAnnAssign(self.env, node)
            if name and var_tp:
                self.env.add_var(name, var_tp)
                self.tp.add_attribute(name, var_tp)
                logger.debug(
                    f'Add class attribute: {self.env.current_uri}.{name}, type: {var_tp}'
                )

    def visit_FunctionDef(self, node: ast.FunctionDef):
        ClassFuncDefVisitor(self.env, self.tp).accept(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        if not self.env.lookup_local_var(node.name):
            ClassDefVisitor(self.env).accept(node)
        else:
            self.env.add_err(node, f'{node.name} already defined')


class TypeBinder(BaseVisitor):
    """Bind name to their type according to the type annotation"""
    def __init__(self, env: Environment):
        super().__init__()
        self.env = env

    def accept(self, node: ast.AST):
        self.visit(node)

    def visit_Assign(self, node: ast.Assign):
        if not is_special_typing(node):
            res = _def_visitAssign(self.env, node)
            for name, tp in res.items():
                self.env.add_var(name, tp)
                logger.debug(f'Add {self.env.current_uri}.{name}, type: {tp}')

    def visit_AnnAssign(self, node: ast.AnnAssign):
        if not is_special_typing(node):
            name, tp = _def_visitAnnAssign(self.env, node)
            if name and tp:
                self.env.add_var(name, tp)
                logger.debug(f'Add {self.env.current_uri}.{name}, type: {tp}')

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
        else:
            self.env.add_err(node, node.name)


def _def_visitAssign(env: Environment, node: ast.Assign):
    """Get the variables defined in an ast.Assign node"""
    new_var = OrderedDict()
    com_tp = parse_comment_annotation(node, env)
    assign_tp = com_tp if com_tp else any_type
    for sub_node in reversed(node.targets):
        if isinstance(sub_node, ast.Name):
            if not env.lookup_local_var(
                    sub_node.id) and sub_node.id not in new_var:
                # this assignment is also a definition
                new_var[sub_node.id] = assign_tp
    return new_var


def _def_visitAnnAssign(env: Environment, node: ast.AnnAssign):
    """Get the variables defined in an ast.AnnAssign node"""
    tp = parse_annotation(node.annotation, env)
    assign_tp = tp if tp else any_type.instantiate([])
    if isinstance(node.target, ast.Name):
        if not env.lookup_local_var(node.target.id):
            # this assignment is also a definition
            return node.target.id, assign_tp
    return None, None
