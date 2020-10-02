import ast
import os
import logging
from contextlib import contextmanager
from pystatic.arg import Arg, Argument
from typing import List, Tuple
from pystatic.target import Target
from pystatic.uri import uri2list
from pystatic.util import split_import_stmt
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
    urilist = uri2list(target.uri)
    cur_dir = rt_dir

    for i, name in enumerate(urilist):
        next_dir = os.path.join(cur_dir, name)
        if not os.path.exists(next_dir):
            if i != len(urilist) - 1:
                os.mkdir(next_dir)

        cur_dir = next_dir

    return cur_dir + '.pyi'


def stubgen_main(target: Target) -> str:
    creator = StubGen(target)
    return creator.generate()


class Node:
    def __init__(self, uri: str):
        self.uri = uri
        self.suburi = {}
        self.alias = None

    def set_alias(self, alias: str):
        self.alias = alias


class NameTree:
    def __init__(self, module_uri: str):
        self.root = Node('')
        self.module_uri = module_uri

    def ask(self, temp: TypeTemp) -> str:
        module_uri = temp.module_uri
        uri = temp.name

        urilist = uri2list(module_uri) + uri2list(uri)
        cur_node = self.root
        namelist = []
        for subname in urilist:
            if subname in cur_node.suburi:
                cur_node = cur_node.suburi[subname]
                if cur_node.alias:
                    namelist = [cur_node.alias]
                else:
                    namelist.append(subname)
            else:
                return '.'.join(urilist)
        return '.'.join(namelist)

    def add_import(self, module_uri: str, uri: str, asname: str):
        urilist = uri2list(module_uri) + uri2list(uri)
        cur_node = self.root

        for subname in urilist:
            if not subname:
                continue
            if subname in cur_node.suburi:
                cur_node = cur_node.suburi[subname]
            else:
                cur_node.suburi[subname] = Node(subname)

        if asname:
            cur_node.alias = asname


class StubGen:
    def __init__(self, target: Target):
        self.target = target
        self.name_tree = NameTree(target.uri)
        self.in_class = False
        self.from_typing = []
        self.cur_uri = ''

    @property
    def module_uri(self):
        return self.target.uri

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
        impt_typing = ', '.join(self.from_typing)
        if impt_typing:
            return f'from typing import {impt_typing}\n' + src_str
        else:
            return src_str

    @contextmanager
    def enter_class(self, clsname: str):
        old_uri = self.cur_uri
        old_in_class = self.in_class
        if not self.cur_uri:
            self.cur_uri = f'{clsname}'
        else:
            self.cur_uri += f'.{clsname}'
        yield
        self.cur_uri = old_uri
        self.in_class = old_in_class

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
            impt_dict = split_import_stmt(impt_node, symtable.glob_uri)
            if isinstance(impt_node, ast.Import):
                import_stmt = 'import '
                import_subitem = []
                for uri, infolist in impt_dict.items():
                    module_name = uri

                    for asname, origin_name in infolist:
                        assert not origin_name
                        if asname == module_name:
                            top_name = uri2list(asname)[0]
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
                for uri, infolist in impt_dict.items():
                    module_name = uri
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
        module_uri = temp.module_uri
        uri = temp.name
        type_str = ''

        if module_uri == 'builtins':
            type_str = uri

        elif module_uri == 'typing':
            type_str = module_uri + '.' + uri

        elif module_uri == self.module_uri:
            if self.cur_uri and uri.find(
                    self.cur_uri) == 0 and len(uri) > len(self.cur_uri):
                type_str = uri[len(self.cur_uri) + 1:]
            else:
                type_str = uri

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

    def stub_fun_def(self,
                     funname: str,
                     temp: TypeFuncTemp,
                     level: int,
                     is_method=False) -> str:
        def get_arg_str(arg: Arg):
            cur_str = arg.name
            cur_str += ': ' + str(arg.ann)
            if arg.valid:
                cur_str += '=...'
            return cur_str

        arg_strlist = []
        for arg in temp.argument.args:
            cur_str = get_arg_str(arg)
            arg_strlist.append(cur_str)

        if temp.argument.vararg:
            cur_str = get_arg_str(temp.argument.vararg)
            arg_strlist.append(cur_str)

        for arg in temp.argument.kwonlyargs:
            cur_str = get_arg_str(arg)
            arg_strlist.append(cur_str)

        if temp.argument.kwarg:
            cur_str = get_arg_str(temp.argument.kwarg)
            arg_strlist.append(cur_str)

        param = '(' + ', '.join(arg_strlist) + ')'

        return _indent_unit * level + 'def ' + funname + param + ': ...\n'
