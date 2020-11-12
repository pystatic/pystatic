import ast
import sys
import os
from collections import namedtuple

sys.path.extend(['.', '..'])

from pystatic.typesys import TypeIns, TypeType
from pystatic.predefined import TypeModuleTemp
from pystatic.config import Config
from pystatic.manager import Manager
from pystatic.exprparse import eval_expr


def parse_file(file_path):
    with open(file_path) as f:
        lines = f.readlines()
    MsgWithLine = namedtuple("MsgWithLine", ["lineno", "msg"])
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


file_list = [
    'check_assign',
    'check_attribute',
    'check_reach'
]


def test_check():
    for src in file_list:
        cwd = os.path.dirname(__file__)
        config = Config({'cwd': cwd})
        manager = Manager(config)
        file_path = os.path.join(cwd, 'src', 'check', f'{src}.py')
        res_option = manager.add_check_file(file_path)
        assert res_option.value
        manager.preprocess()
        manager.infer()
        mbox = manager.get_mbox(file_path)
        msg_list = parse_file(file_path)
        for true_msg, test_msg in zip(msg_list, mbox.error):
            assert true_msg.lineno == test_msg.lineno, src
            assert true_msg.msg == test_msg.msg, src

        assert len(msg_list) == len(mbox.error), src
