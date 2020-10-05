import argparse
import sys
from typing import TextIO, List
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
                        metavar='package path',
                        help='package path',
                        type=str)
    parser.add_argument('--stubgen',
                        action='store_true',
                        help='generate stub files')
    parse_res = parser.parse_args()
    return parse_res


def cmdline(stdout: TextIO, stderr: TextIO, load_typeshed=True):
    cmd_res = cmdline_parse()
    if not cmd_res.module:
        cmd_res.module = []
    if not cmd_res.package:
        cmd_res.package = []
    manager = Manager(cmd_res, cmd_res.module, cmd_res.package, stdout, stderr,
                      load_typeshed)
    if cmd_res.stubgen:
        manager.stubgen()
    else:
        manager.start_check()


def test_pystatic(config: dict, src: List[str], load_typeshed: bool = True):
    manager = Manager(config, src, [], sys.stdout, sys.stderr, load_typeshed)
    manager.start_check()


def test_stubgen(config: dict, src: List[str], load_typeshed: bool = True):
    manager = Manager(config, src, [], sys.stdout, sys.stderr, load_typeshed)
    manager.stubgen()


if __name__ == '__main__':
    cmdline(sys.stdout, sys.stderr)
