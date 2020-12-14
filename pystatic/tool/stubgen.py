import ast
import os
import logging
from contextlib import contextmanager
from pystatic.arg import Arg, Argument
from typing import List, Tuple
from pystatic.target import Target
from pystatic.symid import symid2list
from pystatic.typesys import TypeClassTemp, TypeFuncTemp, TypeIns, TypeTemp, TypeType
from pystatic.symtable import SymTable

logger = logging.getLogger(__name__)

_default_dir = os.path.curdir + os.path.sep + 'out'
_indent_unit = ' ' * 4

IMPORT = 1
FUN = 2
CLS = 3
VAR = 4


def stubgen(targets: List[Target], rt_dir=_default_dir):
    if not mkstub_dir(rt_dir):
        return

    for target in targets:
        stub_file = filepath(target, rt_dir)

        result = stubgen_main(target)

        with open(stub_file, 'w') as f:
            f.write(result)


def mkstub_dir(dir: str):
    if os.path.exists(dir):
        if not os.path.isdir(dir):
            r_path = os.path.realpath(dir)
            logger.error(f'{r_path} already exists and is a file.')
            return False
        return True
    else:
        os.mkdir(dir)
        return True


def filepath(target: Target, rt_dir: str):
    symidlist = symid2list(target.symid)
    cur_dir = rt_dir

    for i, name in enumerate(symidlist):
        next_dir = os.path.join(cur_dir, name)
        if not os.path.exists(next_dir):
            if i != len(symidlist) - 1:
                os.mkdir(next_dir)

        cur_dir = next_dir

    return cur_dir + '.pyi'


def stubgen_main(target: Target) -> str:
    creator = StubGen(target)
    return creator.generate()


class Node:
    def __init__(self, symid: str):
        self.symid = symid
        self.subsymid = {}
        self.alias = None

    def set_alias(self, alias: str):
        self.alias = alias


class NameTree:
    def __init__(self, module_symid: str):
        self.root = Node('')
        self.module_symid = module_symid

    def ask(self, temp: TypeTemp) -> str:
        module_symid = temp.module_symid
        symid = temp.name

        symidlist = symid2list(module_symid) + symid2list(symid)
        cur_node = self.root
        namelist = []
        for subname in symidlist:
            if subname in cur_node.subsymid:
                cur_node = cur_node.subsymid[subname]
                if cur_node.alias:
                    namelist = [cur_node.alias]
                else:
                    namelist.append(subname)
            else:
                return '.'.join(symidlist)
        return '.'.join(namelist)

    def add_import(self, module_symid: str, symid: str, asname: str):
        symidlist = symid2list(module_symid) + symid2list(symid)
        cur_node = self.root

        for subname in symidlist:
            if not subname:
                continue
            if subname in cur_node.subsymid:
                cur_node = cur_node.subsymid[subname]
            else:
                cur_node.subsymid[subname] = Node(subname)

        if asname:
            cur_node.alias = asname


class StubGen:
    def __init__(self, target: Target):
        self.target = target
        self.name_tree = NameTree(target.symid)
        self.in_class = False
        self.from_typing = set()
        self.cur_symid = ''

    @property
    def module_symid(self):
        return self.target.symid

    @staticmethod
    def scoped_list_to_str(lst: List[Tuple[str, int]]):
        if not lst:
            return ''
        results = [lst[0][0]]
        prev_scope = lst[0][1]
        for item, scope in lst[1:]:
            if prev_scope == scope:
                results.append(item)
            else:
                results.append('\n')
                results.append(item)
            prev_scope = scope

        return ''.join(results)

    def generate(self):
        src_str = self.stubgen_symtable(self.target.symtable, 0)
        sym_local = self.target.symtable.local
        typing_list = filter(
            lambda name: (name not in sym_local) and name.find('.') < 0,
            self.from_typing)
        impt_typing = ', '.join(typing_list)
        if impt_typing:
            return f'from typing import {impt_typing}\n' + src_str
        else:
            return src_str

    @contextmanager
    def enter_class(self, clsname: str):
        old_symid = self.cur_symid
        old_in_class = self.in_class
        if not self.cur_symid:
            self.cur_symid = f'{clsname}'
        else:
            self.cur_symid += f'.{clsname}'
        yield
        self.cur_symid = old_symid
        self.in_class = old_in_class

    def indent_prefix(self, level: int) -> str:
        return _indent_unit * level

    def stubgen_symtable(self, symtable: 'SymTable', level: int):
        results: List[Tuple[str, int]] = []
        impt_stmt = self.stubgen_import(symtable, level)
        if impt_stmt:
            results.append((impt_stmt, IMPORT))

        for name, entry in symtable.local.items():
            tpins = entry.get_type()
            if not tpins:
                logger.warn(f'{name} has incomplete type.')
                continue

            temp = tpins.temp
            if isinstance(tpins, TypeType):
                assert isinstance(temp, TypeClassTemp)
                results.append((self.stub_cls_def(name, temp, level), CLS))
            elif isinstance(temp, TypeFuncTemp):
                results.append((self.stub_fun_def(name, temp, level), FUN))
            else:
                results.append((self.stub_var_def(name, temp, level), VAR))

        return self.scoped_list_to_str(results)

    def stubgen_import(self, symtable: 'SymTable', level: int) -> str:
        results = []
        for impt_node in symtable._import_nodes:
            impt_dict = split_import_stmt(impt_node, symtable.glob_symid)
            if isinstance(impt_node, ast.Import):
                import_stmt = 'import '
                import_subitem = []
                for symid, infolist in impt_dict.items():
                    module_name = symid

                    for asname, origin_name in infolist:
                        assert not origin_name
                        if asname == module_name:
                            top_name = symid2list(asname)[0]
                            if top_name:
                                symtable.local.pop(top_name, None)

                            import_subitem.append(f'{module_name}')
                            self.name_tree.add_import(module_name, '', '')
                        else:
                            symtable.local.pop(asname, None)

                            import_subitem.append(f'{module_name} as {asname}')
                            self.name_tree.add_import(module_name, '', asname)

                if len(import_subitem) > 5:
                    import_stmt += '(' + ', '.join(import_subitem) + ')'
                else:
                    import_stmt += ', '.join(import_subitem)
                results.append((import_stmt, level))

            else:
                for symid, infolist in impt_dict.items():
                    module_name = symid
                    from_impt: List[str] = []

                    for asname, origin_name in infolist:
                        if origin_name == asname:
                            symtable.local.pop(asname, None)

                            from_impt.append(f"{asname}")
                            self.name_tree.add_import(module_name, origin_name,
                                                      '')
                        else:
                            symtable.local.pop(asname, None)

                            from_impt.append(f"{origin_name} as {asname}")
                            self.name_tree.add_import(module_name, origin_name,
                                                      asname)

                    if from_impt:
                        impt_str = ', '.join(from_impt)
                        if len(from_impt) > 5:
                            from_stmt = f'from {module_name} import ({impt_str})'
                        else:
                            from_stmt = f'from {module_name} import {impt_str}'
                        results.append((from_stmt, level))
        if not results:
            return ''
        else:
            return '\n'.join(
                [_indent_unit * ident + stmt
                 for stmt, ident in results]) + '\n'

    def stub_var_def(self, varname: str, temp: TypeTemp, level: int):
        module_symid = temp.module_symid
        symid = temp.name
        type_str = ''

        if module_symid == 'builtins':
            type_str = symid

        elif module_symid == 'typing':
            self.from_typing.add(symid)
            type_str = symid

        elif module_symid == self.module_symid:
            if self.cur_symid and symid.find(
                    self.cur_symid) == 0 and len(symid) > len(self.cur_symid):
                type_str = symid[len(self.cur_symid) + 1:]
            else:
                type_str = symid

        else:
            type_str = self.name_tree.ask(temp)

        return _indent_unit * level + varname + ': ' + type_str + '\n'

    def stub_cls_def(self, clsname: str, temp: TypeClassTemp, level: int):
        header = self.stub_cls_def_header(clsname, temp, level)

        inner_symtable = temp.get_inner_symtable()
        var_strlist = []
        with self.enter_class(clsname):
            for name, tpins in temp.var_attr.items():
                var_strlist.append(
                    self.stub_var_def(name, tpins.temp, level + 1))

            body = self.stubgen_symtable(inner_symtable, level + 1)

        if not body or body == '\n':
            header += '...\n'
            return header

        if var_strlist:
            body = ''.join(var_strlist) + '\n' + body

        return header + '\n' + body

    def stub_cls_def_header(self, clsname: str, temp: TypeClassTemp,
                            level: int) -> str:
        return _indent_unit * level + 'class ' + clsname + ': '

    def _stub_single_fun(self, name: str, argument: Argument, ret: TypeIns):
        """generate single function type annotations in pyi file"""
        def get_arg_str(arg: Arg):
            cur_str = arg.name
            cur_str += ': ' + str(arg.ann)
            if arg.valid:
                cur_str += '=...'
            return cur_str

        arg_strlist = []
        for arg in argument.args:
            cur_str = get_arg_str(arg)
            arg_strlist.append(cur_str)

        if argument.vararg:
            cur_str = get_arg_str(argument.vararg)
            arg_strlist.append(cur_str)

        for arg in argument.kwonlyargs:
            cur_str = get_arg_str(arg)
            arg_strlist.append(cur_str)

        if argument.kwarg:
            cur_str = get_arg_str(argument.kwarg)
            arg_strlist.append(cur_str)

        param = '(' + ', '.join(arg_strlist) + ')'

        return 'def ' + name + param + ': ...\n'

    def stub_fun_def(self,
                     funname: str,
                     temp: TypeFuncTemp,
                     level: int,
                     is_method=False) -> str:
        is_overload = len(temp.overloads) > 1
        if is_overload:
            self.from_typing.add('overload')  # import overload from typing

        indent_prefix = self.indent_prefix(level)

        fun_pyi = []
        for argument, ret in temp.overloads:
            fun_res = self._stub_single_fun(funname, argument, ret)
            if is_overload:
                cur_fun_pyi = indent_prefix + '@overload\n'
            else:
                cur_fun_pyi = ''
            cur_fun_pyi += indent_prefix + fun_res
            fun_pyi.append(cur_fun_pyi)

        return ''.join(fun_pyi)
