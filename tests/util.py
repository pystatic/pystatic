import sys

sys.path.extend([".", ".."])

import os
from collections import namedtuple
from pystatic.manager import Manager
from pystatic.config import Config
from typing import Optional, Tuple

MsgWithLine = namedtuple("MsgWithLine", ["lineno", "msg"])


def error_assert(symid: str, precise: bool = True):
    """Assert based on error annotation in the file

    @param symid: symbol id of the target module.

    @param precise: True for precise match, and False for just a subset.
    """
    manager, path = get_manager_path({}, symid)
    manager.preprocess()
    manager.infer()

    true_msg_list = parse_file_error(path)
    mbox = manager.get_mbox_by_symid(symid)
    test_msg_list = mbox.to_message()

    if precise:
        assert len(true_msg_list) == len(test_msg_list)
        for true_msg, test_msg in zip(true_msg_list, test_msg_list):
            assert test_msg.lineno == true_msg.lineno
            assert test_msg.msg == true_msg.msg
    else:
        true_msg_list = [(true_msg.lineno, true_msg.msg) for true_msg in true_msg_list]
        test_msg_list = [(test_msg.lineno, test_msg.msg) for test_msg in test_msg_list]
        for true_msg in true_msg_list:
            assert true_msg in test_msg_list


def parse_file_error(file_path):
    with open(file_path) as f:
        lines = f.readlines()
    msg_list = []

    lineno = 1
    for line in lines:
        line = line.strip()
        if line.startswith('#') and not line.startswith('# E'):
            lineno += 1
            continue
        index = line.find("# E")
        if index != -1:
            msg = line[index + 4 :]
            msg_list.append(MsgWithLine(lineno, msg))
        lineno += 1
    return msg_list


def check_error_msg(mbox, true_msg_list):
    test_msg_list = mbox.to_message()
    assert len(test_msg_list) == len(true_msg_list)
    for true_msg, test_msg in zip(true_msg_list, test_msg_list):
        assert test_msg.lineno == true_msg.lineno
        assert test_msg.msg == true_msg.msg


def get_manager_path(
    config: dict, symid: str, cwd: Optional[str] = None
) -> Tuple["Manager", str]:
    if not cwd:
        # default root path for checked files is tests/src/
        cwd = os.path.join(os.path.dirname(__file__), "src")
    filepath = os.path.join(cwd, *(symid.split("."))) + ".py"
    config["cwd"] = cwd
    manager = Manager(Config(config))
    manager.add_check_file(filepath)
    return manager, filepath
