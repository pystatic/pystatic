import os
import logging
from pystatic.arg import Arg, Argument
from typing import List, Tuple
from pystatic.target import Target
from pystatic.uri import uri2list
from pystatic.typesys import TypeClassTemp, TypeFuncTemp, TypeIns, TypeTemp, TypeType
from pystatic.symtable import SymTable

logger = logging.getLogger(__name__)

_default_dir = os.path.curdir + os.path.sep + 'out'
_indent_unit = ' ' * 4
IndentedStr = Tuple[str, int]


def stubgen(targets: List[Target], rt_dir=_default_dir):
    mkstub_dir(rt_dir)

    for target in targets:
        stub_file = filepath(target, rt_dir)

        result = stubgen_main(target)

        with open(stub_file, 'w') as f:
            f.write(result)


def mkstub_dir(dir: str):
    if os.path.exists(dir):
        if not os.path.isdir(dir):
            raise OSError  # TODO: report error and quit.
    else:
        os.mkdir(dir)


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
    idstr_list = _stubgen_symtable(target.symtable, 0)
    str_list = [indented_to_str(item) for item in idstr_list]
    return '\n'.join(str_list)


def _stubgen_symtable(symtable: 'SymTable', level: int) -> List[IndentedStr]:
    results: List[IndentedStr] = []
    for name, entry in symtable.local.items():
        tpins = entry.get_type()
        if not tpins:
            # TODO: warning here
            logger.warn(f'{name} has incomplete type.')
            continue

        results += ins_to_idstrlist(name, tpins, level)

    return results


def ins_to_idstrlist(name: str, tpins: TypeIns,
                     level: int) -> List[IndentedStr]:
    temp = tpins.temp
    if isinstance(tpins, TypeType):
        return stub_cls_def(name, temp, level)  # type: ignore
    else:
        if isinstance(temp, TypeFuncTemp):
            return [stub_fun_def(name, temp, level)]
        else:
            return [(name + ': ' + str(tpins), level)]


def stub_var_def(varname: str, temp: TypeTemp, level: int) -> IndentedStr:
    return varname + ': ' + str(temp), level


def stub_cls_def(clsname: str, temp: TypeClassTemp,
                 level: int) -> List[IndentedStr]:
    header = stub_cls_def_header(clsname, temp, level)

    var_strlist = []
    for name, tpins in temp.var_attr.items():
        var_strlist.append(stub_var_def(name, tpins.temp, level + 1))

    inner_symtable = temp.get_inner_symtable()
    body = _stubgen_symtable(inner_symtable, level + 1)

    if not body:
        header = (header[0] + ' ...', header[1])

    return [header] + var_strlist + body


def stub_cls_def_header(clsname: str, temp: TypeClassTemp,
                        level: int) -> IndentedStr:
    return ('class ' + clsname + ':', level)


def stub_fun_def(funname: str, temp: TypeFuncTemp, level: int) -> IndentedStr:
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
