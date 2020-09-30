import os
import logging
from typing import List
from pystatic.target import Target
from pystatic.uri import uri2list
from pystatic.typesys import TypeIns, TypeTemp, TypeType
from pystatic.symtable import SymTable

logger = logging.getLogger(__name__)

_default_dir = os.path.curdir + os.path.sep + 'out'


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


def stubgen_main(target: Target) -> str:
    symtb = target.symtable
    results = []
    for name, entry in symtb.local.items():
        tpins = entry.get_type()
        if not tpins:
            # TODO: warning here
            logger.warn(f'{name} has incomplete type.')
            continue

        results.append(ins_to_str(name, tpins))

    return '\n'.join(results)


def find_in_symtable(tpins: TypeIns, symtable: 'SymTable'):
    for name, entry in symtable.local.items():
        entry_type = entry.get_type()
        if isinstance(entry_type, TypeType):
            if tpins.temp == entry_type.temp:
                return name
    return ''


def ins_to_str(name: str, tpins: TypeIns) -> str:
    return name + ': ' + str(tpins)
