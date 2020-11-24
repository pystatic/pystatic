import sys
sys.path.extend(['.', '..'])

import os
from collections import namedtuple
from pystatic.manager import Manager
from pystatic.config import Config
from typing import Optional, Tuple

MsgWithLine = namedtuple("MsgWithLine", ["lineno", "msg"])


def parse_file_error(file_path):
    with open(file_path) as f:
        lines = f.readlines()
    msg_list = []

    lineno = 1
    for line in lines:
        line = line.strip()
        index = line.find("# E")
        if index != -1:
            msg = line[index + 4:]
            msg_list.append(MsgWithLine(lineno, msg))
        lineno += 1
    return msg_list


def get_manager_path(config: dict,
                     symid: str,
                     cwd: Optional[str] = None) -> Tuple['Manager', str]:
    if not cwd:
        # default root path for checked files is tests/src/
        cwd = os.path.join(os.path.dirname(__file__), 'src')
    filepath = os.path.join(cwd, *(symid.split('.'))) + '.py'
    config['cwd'] = cwd
    manager = Manager(Config(config))
    manager.add_check_file(filepath)
    return manager, filepath
