import ast
import logging
from typing import Optional, List, Union
from collections import OrderedDict
from .env import Environment, get_init_env
from .error import ErrHandler
from .visitor import BaseVisitor, ParseException
from .typesys import (TypeModuleTemp, any_type, TypeVar, TypeClassTemp,
                      TypeFunc, TypePackageTemp)
from .fsys import File, find_module
from .arg import Arg, Argument
from .semanal_parse import typenode_parse_type, TypeNodeTag, get_type

logger = logging.getLogger(__name__)


def _is_typevar_def(node: Union[ast.Assign, ast.AnnAssign]):
    try:
        if not isinstance(node.value, ast.Call):
            return False
        f_name = node.value.func.id
        return f_name == 'TypeVar'
    except AttributeError:
        return False


class ClassCollector(BaseVisitor):
    """Build a TypeScope tree"""
    def __init__(self, env: Environment, err: ErrHandler):
        self.env = env
        self.err = err
        self.met_gen = False

    def _check_appliable(self, node, tp, param_cnt: int):
        """Check whether the number of parameters match the type's definition
        If list is empty then we still consider it a valid match because the
        default is all Any.

        However, for Optional, you must specify a type.
        """
        if tp.name == 'Optional':  # special judge
            assert tp.arity == 1
            if param_cnt != tp.arity:
                raise ParseException(node,
                                     f'Optional require {tp.arity} parameter')
            return True

        if tp.arity < 0:
            if param_cnt <= 0:
                raise ParseException(
                    node, f'{tp.name} require at least one type parameter')
            else:
                return True
        elif tp.arity == param_cnt or param_cnt == 0:
            return True
        else:
            raise ParseException(
                node, f'{tp.name} require {tp.arity} but {param_cnt} given')

    def _extract_type_var(self, node, var_set, var_list):
        def _get_check_typevar(name):
            nonlocal var_set, var_list
            tp = self.env.lookup_type(name)
            if tp is None:
                raise ParseException(node.node, f'{name} is unbound')
            elif isinstance(tp, TypeVar):
                if name not in var_set:
                    if self.met_gen:
                        raise ParseException(node.node,
                                             'all typevar should in Generic')
                    else:
                        var_list.append(name)
                        var_set.add(name)
            return tp

        ast_node = node.node

        if node.tag == TypeNodeTag.ATTR:
            self._extract_type_var(node.left, var_set, var_list)
            return _get_check_typevar(node.name)
        elif node.tag == TypeNodeTag.NAME:
            return _get_check_typevar(node.name)
        elif node.tag == TypeNodeTag.SUBS:
            tp = _get_check_typevar(node.name)
            self._extract_type_var(node.left, var_set, var_list)
            if node.name == 'Generic':
                if self.met_gen:
                    raise ParseException(ast_node, 'only one Generic allowed')
                self.met_gen = True

                var_list.clear()
                gen_set = set()
                for sub_node in node.param:
                    tp_var = self.env.lookup_type(sub_node.name)
                    if not isinstance(tp_var, TypeVar):
                        raise ParseException(
                            ast_node, 'only typevar allowed inside Generic')
                    else:
                        if sub_node.name in gen_set:
                            raise ParseException(
                                ast_node, f'duplicate typevar {sub_node.name}')
                        gen_set.add(sub_node.name)
                        var_list.append(sub_node.name)

                if len(var_set - gen_set) > 0:
                    free_var = list(var_set - gen_set)
                    raise ParseException(
                        ast_node,
                        f'{", ".join(free_var)} should inside Generic')
                var_set = gen_set
            else:
                for sub_node in node.param:
                    self._extract_type_var(sub_node, var_set, var_list)
                self._check_appliable(ast_node, tp, len(node.param))
            return tp
        elif node.tag == TypeNodeTag.LIST:
            for sub_node in node.param:
                self._extract_type_var(sub_node, var_set, var_list)
            return None
        elif node.tag == TypeNodeTag.ELLIPSIS:
            pass
        else:
            raise ParseException(ast_node, 'invalid syntax')

    def extract_type_var(self, node: ast.ClassDef):
        var_list = []
        var_set = set()
        base_list = []
        for base in node.bases:
            self.met_gen = False
            try:
                new_tree = typenode_parse_type(base, False, None)
                self._extract_type_var(new_tree, var_set, var_list)
                base_list.append(get_type(new_tree, self.env))
            except ParseException as e:
                msg = e.msg if e.msg else 'invalid base class'
                if e.msg:
                    self.err.add_err(e.node, msg)
        return var_list, base_list

    def visit_ClassDef(self, node: ast.ClassDef):
        if not self.env.lookup_local_type(node.name):
            cls_uri = self.env.absolute_name + f'.{node.name}'
            tp = TypeClassTemp(cls_uri)
            var_lst, base_list = self.extract_type_var(node)
            tpvar_dict = OrderedDict()
            for tpvar_name in var_lst:
                tpvar = self.env.lookup_type(tpvar_name)
                assert isinstance(tpvar, TypeVar)
                tpvar_dict[tpvar_name] = tpvar
            tp.set_typevar(tpvar_dict)
            for base_tp in base_list:
                tp.add_base(base_tp.name, base_tp)
                logger.debug(f'Add base class {base_tp.name} to {cls_uri}')
            self.env.add_type(node.name, tp)
            logger.debug(
                f'Add class type {cls_uri}, arity: {tp.arity} {",".join(var_lst)}'
            )
            self.env.enter_class(node.name)
            for sub_node in node.body:
                self.visit(sub_node)  # try to get nested class
            self.env.pop_scope()

    def visit_Assign(self, node: ast.Assign):
        if _is_typevar_def(node):
            for sub_node in node.targets:
                if isinstance(sub_node, ast.Name):
                    if not self.env.lookup_local_type(sub_node.id):
                        var_uri = self.env.absolute_name + f'.{sub_node.id}'
                        self.env.add_type(sub_node.id, TypeVar(sub_node.id))
                        logger.debug(f'Add type var: {var_uri}')

    def visit_AnnAssign(self, node: ast.AnnAssign):
        if _is_typevar_def(node):
            target = node.target
            if isinstance(target, ast.Name):
                if not self.env.lookup_local_type(str(node)):
                    var_uri = self.env.absolute_name + f'.{target.id}'
                    self.env.add_type(target.id, TypeVar(target.id))
                    logger.debug(f'Add type var: {var_uri}')

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            m_file = find_module(alias.name, self.env.file)
            if m_file is None:
                self.err.add_err(node, f'module {alias.name} not found')
            else:
                m_type = semanal_module(m_file)
                name = alias.asname if alias.asname else alias.name
                self.env.add_type(name, m_type)
                logger.debug(
                    f'Import {alias.name} as {name} (abspath: {m_file.abs_path})'
                )

    def visit_ImportFrom(self, node: ast.ImportFrom):
        modulename = node.module if node.module else ''
        modulename = '.' * node.level + modulename
        m_file = find_module(modulename, self.env.file)
        if m_file is None:
            self.err.add_err(node, f'module {modulename} not found')
        else:
            m_type = semanal_module(m_file)
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name
                res = m_type.get_type(name)
                if res is None:
                    self.err.add_err(alias,
                                     f'{modulename}.{alias.name} not found')
                else:
                    self.env.add_type(name, res)


class AnnotationParser(object):
    """Parse annotations"""
    def __init__(self, env: Environment, err: ErrHandler):
        self.env = env
        self.err = err

    def accept(self, node: ast.AST):
        """Return the type this node represents"""
        try:
            new_tree = typenode_parse_type(node, False, None)
            return get_type(new_tree, self.env)
        except ParseException as e:
            self.err.add_annotation(e.node, e.msg)
            return None


def _ann_to_type(node: ast.AST, env: Environment, err: ErrHandler):
    """Get the type according to the annotation"""
    return AnnotationParser(env, err).accept(node)


def _comment_to_type(node: ast.AST, env: Environment, err: ErrHandler):
    """Get the type according to the type comment"""
    comment = node.type_comment if node.type_comment else None
    if not comment:
        return None
    try:
        node = ast.parse(
            comment,
            mode='eval')  # for annotations that's str we first parse it
        if isinstance(node, ast.Expression):
            return AnnotationParser(env, err).accept(node.body)
        else:
            raise ParseException(node, '')
    except (SyntaxError, ParseException):
        err.add_annotation(node, 'broken type comment')
        return None


def _parse_arg(node: ast.arg, tp_scope: Environment, err: ErrHandler):
    """Generate an Arg instance according to an ast.arg node"""
    new_arg = Arg(node.arg)
    if node.annotation:
        ann = _ann_to_type(node.annotation, tp_scope, err)
        if not ann:
            return None
        else:
            new_arg.ann = ann
    return new_arg


def _parse_arguments(node: ast.arguments, tp_scope: Environment,
                     err: ErrHandler) -> Optional[Argument]:
    """Gernerate an Argument instance according to an ast.arguments node"""
    new_args = Argument()
    # order_arg: [**posonlyargs, **args]
    # order_kwarg: [**kwonlyargs]
    # these two lists are created to deal with default values
    order_arg: List[Arg] = []
    order_kwarg: List[Arg] = []
    ok = True

    # parse a list of args
    def add_to_list(target_list, order_list, args):
        global ok
        for arg in args:
            gen_arg = _parse_arg(arg, tp_scope, err)
            if gen_arg:
                target_list.append(gen_arg)
                order_list.append(gen_arg)
            else:
                ok = False

    add_to_list(new_args.posonlyargs, order_arg, node.posonlyargs)
    add_to_list(new_args.args, order_arg, node.args)
    add_to_list(new_args.kwonlyargs, order_kwarg, node.kwonlyargs)

    # *args exists
    if node.vararg:
        result = _parse_arg(node.vararg, tp_scope, err)
        if result:
            new_args.vararg = result
        else:
            ok = False

    # **kwargs exists
    if node.kwarg:
        result = _parse_arg(node.kwarg, tp_scope, err)
        if result:
            new_args.kwarg = result
        else:
            ok = False

    for arg, value in zip(reversed(order_arg), reversed(node.defaults)):
        arg.valid = True
        arg.default = value  # TODO: add type check here

    for arg, value in zip(reversed(order_kwarg), reversed(node.kw_defaults)):
        arg.valid = True
        arg.default = value  # TODO: add type check here(here value is a node represent an expression)

    if ok:
        return new_args
    else:
        return None


def _def_visitAssign(env: Environment, err: ErrHandler, node: ast.Assign):
    """Get the variables defined in an ast.Assign node"""
    new_var = OrderedDict()
    com_tp = _comment_to_type(node, env, err)
    assign_tp = com_tp if com_tp else any_type
    for sub_node in reversed(node.targets):
        if isinstance(sub_node, ast.Name):
            if not env.lookup_local_var(
                    sub_node.id) and sub_node.id not in new_var:
                # this assignment is also a definition
                new_var[sub_node.id] = assign_tp
    return new_var


def _def_visitAnnAssign(env: Environment, err: ErrHandler,
                        node: ast.AnnAssign):
    """Get the variables defined in an ast.AnnAssign node"""
    tp = _ann_to_type(node.annotation, env, err)
    assign_tp = tp if tp else any_type.instantiate([])
    if isinstance(node.target, ast.Name):
        if not env.lookup_local_var(node.target.id):
            # this assignment is also a definition
            return node.target.id, assign_tp
    return None, None


def _get_func_type(node: ast.FunctionDef, env: Environment,
                   err: ErrHandler) -> Optional[TypeFunc]:
    """Get a function's type according to a ast.FunctionDef node"""
    argument = _parse_arguments(node.args, env, err)
    if not argument:
        return
    ret_type = None
    if node.returns:
        ret_type = _ann_to_type(node.returns, env, err)
    if not ret_type:
        ret_type = any_type  # default return type is Any
    return TypeFunc(argument, ret_type)


class ClassFuncDefVisitor(BaseVisitor):
    """Visit methods defined in a class and add it to the class type.
    Also collect data members defined inside the class and add them to
    the class type
    """
    def __init__(self, env: Environment, err: ErrHandler, tp):
        self.env = env
        self.err = err
        self.tp = tp

    def accept(self, node: ast.FunctionDef):
        if node.name in self.tp:
            return
        else:
            func_type = _get_func_type(node, self.env, self.err)
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
        com_tp = _comment_to_type(node, self.env, self.err)
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
        tp = _ann_to_type(node.annotation, self.env, self.err)
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
    def __init__(self, env: Environment, err: ErrHandler):
        self.env = env
        self.err = err

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
            self.err.add_redefine(node, node.name)

    def visit_Assign(self, node: ast.Assign):
        if not _is_typevar_def(node):
            res = _def_visitAssign(self.env, self.err, node)
            for name, var_tp in res.items():
                self.env.add_var(name, var_tp)
                self.tp.add_attribute(name, var_tp)
                logger.debug(
                    f'Add class attribute: {self.env.absolute_name}.{name}, type: {var_tp}'
                )

    def visit_AnnAssign(self, node: ast.AnnAssign):
        if not _is_typevar_def(node):
            name, var_tp = _def_visitAnnAssign(self.env, self.err, node)
            if name and var_tp:
                self.env.add_var(name, var_tp)
                self.tp.add_attribute(name, var_tp)
                logger.debug(
                    f'Add class attribute: {self.env.absolute_name}.{name}, type: {var_tp}'
                )

    def visit_FunctionDef(self, node: ast.FunctionDef):
        ClassFuncDefVisitor(self.env, self.err, self.tp).accept(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        if not self.env.lookup_local_var(node.name):
            ClassDefVisitor(self.env, self.err).accept(node)
        else:
            self.err.add_redefine(node, node.name)


class TypeRecorder(BaseVisitor):
    """Bind name to their type according to the type annotation"""
    def __init__(self, env: Environment, err: ErrHandler):
        self.env = env
        self.err = err

    def accept(self, node: ast.AST):
        self.visit(node)

    def visit_Assign(self, node: ast.Assign):
        if not _is_typevar_def(node):
            res = _def_visitAssign(self.env, self.err, node)
            for name, tp in res.items():
                self.env.add_var(name, tp)
                logger.debug(
                    f'Add {self.env.absolute_name}.{name}, type: {tp}')

    def visit_AnnAssign(self, node: ast.AnnAssign):
        if not _is_typevar_def(node):
            name, tp = _def_visitAnnAssign(self.env, self.err, node)
            if name and tp:
                self.env.add_var(name, tp)
                logger.debug(
                    f'Add {self.env.absolute_name}.{name}, type: {tp}')

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if self.env.lookup_local_var(node.name):
            self.err.add_redefine(node, node.name)
            return
        else:
            func_type = _get_func_type(node, self.env, self.err)
            if func_type:
                self.env.add_var(node.name, func_type)
                logger.debug(f'Add function {func_type}')

    def visit_ClassDef(self, node: ast.ClassDef):
        if not self.env.lookup_local_var(node.name):
            ClassDefVisitor(self.env, self.err).accept(node)
        else:
            self.err.add_redefine(node, node.name)


def semanal_module(module: File) -> Union[TypeModuleTemp, TypePackageTemp]:
    """before call it, make sure module is a package or a module"""
    if module.isdir():
        return TypePackageTemp(module)
    else:
        env = get_init_env(module)
        err = ErrHandler(module)
        node = module.parse()
        ClassCollector(env, err).accept(node)
        TypeRecorder(env, err).accept(node)
        return env.to_module()
