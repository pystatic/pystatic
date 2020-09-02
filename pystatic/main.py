import argparse
import os
import sys
from typing import Text, TextIO, List
from pystatic.manager import Manager


def cmdline_parse():
    parser = argparse.ArgumentParser('python static type checker')
    parser.add_argument('module',
                        metavar='module',
                        nargs='+',
                        help='module path',
                        type=str)
    parser.add_argument('-p',
                        '--package',
                        action='append',
                        metavar='package',
                        help='package path',
                        type=str)
    parse_res = parser.parse_args()
    return parse_res


def cmdline(stdout: TextIO, stderr: TextIO):
    cmd_res = cmdline_parse()
    if not cmd_res.module:
        cmd_res.module = []
    if not cmd_res.package:
        cmd_res.package = []
    manager = Manager(cmd_res, cmd_res.module, cmd_res.package, stdout, stderr)
    manager.start_check()


if __name__ == '__main__':
    cmdline(sys.stdout, sys.stderr)
