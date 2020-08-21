import argparse
import os
from typing import TextIO, List
from .fsys import File, ModuleResolution
from .semanal import ClassCollector, TypeRecorder
from .env import get_init_env
from .error import ErrHandler


def check(srcfiles: List[str], stdout: TextIO, stderr: TextIO):
    for file in srcfiles:
        f_check = File(file)
        m_finder = ModuleResolution(f_check.dirname)
        env = get_init_env(f_check)
        err = ErrHandler(f_check)
        treenode = f_check.parse()
        ClassCollector(env, m_finder, err).accept(treenode)
        TypeRecorder(env, err).accept(treenode)

        for e in err:
            stdout.write(str(e) + '\n')


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

    check(srcfiles, stdout, stderr)
