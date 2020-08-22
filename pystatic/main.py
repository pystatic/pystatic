import argparse
import os
from typing import TextIO, List
from pystatic.manager import Manager


def cmdline(stdout: TextIO, stderr: TextIO):
    parser = argparse.ArgumentParser('python static type checker')
    parser.add_argument('path', metavar='files', nargs='+', type=str)
    parse_res = parser.parse_args()
    srcfiles = []

    cwd = os.getcwd()
    for path in parse_res.path:
        if not os.path.isabs(path):
            path = os.path.join(cwd, path)

        if os.path.isdir(path) or os.path.isfile(path):
            srcfiles.append(path)
        else:
            stderr.write(f"{path} doesn't exist\n")

    manager = Manager(parse_res, srcfiles, stdout, stderr)
