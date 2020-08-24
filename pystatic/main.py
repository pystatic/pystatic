import argparse
import os
import sys
from typing import TextIO, List
# from pystatic.manager import Manager


def cmdline():
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
    # for path in parse_res.module:
    #     if not os.path.isabs(path):
    #         path = os.path.join(cwd, path)

    #     if os.path.isdir(path) or os.path.isfile(path):
    #         srcfiles.append(path)
    #     else:
    #         stderr.write(f"{path} doesn't exist\n")

    # manager = Manager(parse_res, srcfiles, stdout, stderr)
    # manager.check()


if __name__ == '__main__':
    cmdline()
