import os
import logging
from typing import List, Tuple
from pystatic.target import Target
from pystatic.uri import uri2list
from pystatic.typesys import TypeClassTemp, TypeIns, TypeTemp, TypeType
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
    if isinstance(tpins, TypeType):
        temp = tpins.temp
        return stub_cls_def(name, temp, level)  # type: ignore
    else:
        return [(name + ': ' + str(tpins), level)]


def stub_cls_def(clsname: str, temp: TypeClassTemp,
                 level: int) -> List[IndentedStr]:
    header = stub_cls_def_header(clsname, temp, level)

    inner_symtable = temp.get_inner_symtable()
    result = _stubgen_symtable(inner_symtable, level + 1)

    if not result:
        header = (header[0] + ' ...', header[1])

    return [header] + result


def stub_cls_def_header(clsname: str, temp: TypeClassTemp,
                        level: int) -> IndentedStr:
    return ('class ' + clsname + ':', level)
