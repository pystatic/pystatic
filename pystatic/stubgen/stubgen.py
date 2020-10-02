import ast
import os
import logging
from pystatic.arg import Arg, Argument
from typing import List, Tuple
from pystatic.target import Target
from pystatic.uri import uri2list
from pystatic.util import split_import_stmt
from pystatic.typesys import TypeClassTemp, TypeFuncTemp, TypeIns, TypeTemp, TypeType
from pystatic.symtable import SymTable
from pystatic.stubgen.clsname import NameTree

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


class StubGen:
    def __init__(self, target: Target):
        self.target = target
        self.name_tree = NameTree(target.uri)
        self.in_class = False

    def generate(self):
        return self.stubgen_symtable(self.target.symtable, 0)

    def enter_class(self):
        pass

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

            if tpins.temp.module_uri == symtable.glob.uri:
                # don't care about symbols that's imported from other module
                temp = tpins.temp
                if isinstance(tpins, TypeType):
                    assert isinstance(temp, TypeClassTemp)
                    results.append((self.stub_cls_def(name, temp, level), CLS))
                elif isinstance(temp, TypeFuncTemp):
                    results.append((self.stub_fun_def(name, temp, level), FUN))
                else:
                    results.append((self.stub_var_def(name, temp, level), VAR))

        return scoped_list_to_str(results)

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
                            import_subitem.append(f'{module_name}')
                            self.name_tree.add_import(module_name, '', '')
                        else:
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
                        # from module_name import ... as ...
                        if origin_name == asname:
                            from_impt.append(f"{asname}")
                            self.name_tree.add_import(module_name, origin_name,
                                                      '')
                        else:
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
        return _indent_unit * level + varname + ': ' + self.name_tree.ask(
            temp) + '\n'

    def stub_cls_def(self, clsname: str, temp: TypeClassTemp, level: int):
        header = self.stub_cls_def_header(clsname, temp, level)

        var_strlist = []
        for name, tpins in temp.var_attr.items():
            var_strlist.append(self.stub_var_def(name, tpins.temp, level + 1))

        inner_symtable = temp.get_inner_symtable()
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
