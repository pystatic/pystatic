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

logger = logging.getLogger(__name__)

_default_dir = os.path.curdir + os.path.sep + 'out'
_indent_unit = ' ' * 4
IndentedStr = Tuple[str, int]


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


def indented_to_str(idstr: IndentedStr):
    return _indent_unit * idstr[1] + idstr[0]


def stubgen_main(target: Target) -> str:
    creator = StubGen(target)
    idstr_list = creator.generate()
    str_list = [indented_to_str(item) for item in idstr_list]
    return '\n'.join(str_list)


class StubGen:
    def __init__(self, target: Target):
        self.target = target

    def generate(self):
        return self.stubgen_symtable(self.target.symtable, 0)

    def stubgen_symtable(self, symtable: 'SymTable',
                         level: int) -> List[IndentedStr]:
        results: List[IndentedStr] = self.stubgen_import(symtable, level)

        for name, entry in symtable.local.items():
            tpins = entry.get_type()
            if not tpins:
                # TODO: warning here
                logger.warn(f'{name} has incomplete type.')
                continue

            if tpins.temp.module_uri == symtable.glob.uri:
                # don't care about symbols that's imported from other module
                results += self.ins_to_idstrlist(name, tpins, level)

        return results

    def stubgen_import(self, symtable: 'SymTable',
                       level: int) -> List[IndentedStr]:
        results = []
        for impt_node in symtable._import_nodes:
            impt_dict = split_import_stmt(impt_node, symtable.glob_uri)
            if isinstance(impt_node, ast.Import):
                import_stmt = 'import '
                import_subitem = []
                for uri, infolist in impt_dict.items():
                    module_name = uri

                    for asname, origin_name in infolist:
                        if not origin_name:
                            if asname == module_name:
                                import_subitem.append(f'{module_name}')
                            else:
                                import_subitem.append(
                                    f'{module_name} as {asname}')

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
                        else:
                            from_impt.append(f"{origin_name} as {asname}")

                    if from_impt:
                        impt_str = ', '.join(from_impt)
                        if len(from_impt) > 5:
                            from_stmt = f'from {module_name} import ({impt_str})'
                        else:
                            from_stmt = f'from {module_name} import {impt_str}'
                        results.append((from_stmt, level))
        return results

    def ins_to_idstrlist(self, name: str, tpins: TypeIns,
                         level: int) -> List[IndentedStr]:
        temp = tpins.temp
        if isinstance(tpins, TypeType):
            assert isinstance(temp, TypeClassTemp)
            return self.stub_cls_def(name, temp, level)
        else:
            if isinstance(temp, TypeFuncTemp):
                return [self.stub_fun_def(name, temp, level)]
            else:
                return [(name + ': ' + str(tpins), level)]

    def stub_var_def(self, varname: str, temp: TypeTemp,
                     level: int) -> IndentedStr:
        return varname + ': ' + str(temp), level

    def stub_cls_def(self, clsname: str, temp: TypeClassTemp,
                     level: int) -> List[IndentedStr]:
        header = self.stub_cls_def_header(clsname, temp, level)

        var_strlist = []
        for name, tpins in temp.var_attr.items():
            var_strlist.append(self.stub_var_def(name, tpins.temp, level + 1))

        inner_symtable = temp.get_inner_symtable()
        body = self.stubgen_symtable(inner_symtable, level + 1)

        if not body:
            header = (header[0] + ' ...', header[1])

        return [header] + var_strlist + body

    def stub_cls_def_header(self, clsname: str, temp: TypeClassTemp,
                            level: int) -> IndentedStr:
        return ('class ' + clsname + ':', level)

    def stub_fun_def(self, funname: str, temp: TypeFuncTemp,
                     level: int) -> IndentedStr:
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

        return ('def ' + funname + param + ': ...', level)
