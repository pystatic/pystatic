import ast
from logging import error
import sys
import os
from collections import namedtuple
from tests.util import error_assert

sys.path.extend([".", ".."])
from pystatic.config import Config
from pystatic.manager import Manager

MsgWithLine = namedtuple("MsgWithLine", ["lineno", "msg"])


def parse_file(file_path):
    with open(file_path) as f:
        lines = f.readlines()
    msg_list = []

    lineno = 1
    for line in lines:
        line = line.strip()
        index = line.find("# E")
        if index != -1:
            msg = line[index + 4 :]
            msg_list.append(MsgWithLine(lineno, msg))
        lineno += 1
    return msg_list


file_list = [
    "check_assign",
    "check_attribute",
    "check_tuple",
    "check_funcdef",
    "check_reach",
    "check_specialfunc",
    "check_for",
]

symid_list = [
    "check.check_assign",
    "check.check_attribute",
    "check.check_tuple",
    "check.check_funcdef",
    "check.check_reach",
    "check.check_specialfunc",
    "check.check_for",
]


def test_check():
    error_assert('check.check_tuple')
    for symid in symid_list:
        error_assert(symid)
    # for src in file_list:
    #     error_assert(src)
    # cwd = os.path.dirname(__file__)
    # config = Config({'cwd': cwd})
    # manager = Manager(config)
    # file_path = os.path.join(cwd, 'src', 'check', f'{src}.py')
    # result = manager.add_check_file(file_path)
    # assert result.value
    # manager.preprocess()
    # manager.infer()
    # errbox = manager.get_mbox(file_path)
    # msg_list = parse_file(file_path)
    # for true_msg, test_msg in zip(msg_list, errbox.to_message()):
    #     assert test_msg.lineno == true_msg.lineno, src
    #     assert test_msg.msg == true_msg.msg, src

    # assert len(errbox.error) == len(msg_list), src
