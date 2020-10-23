import argparse
import os
from pystatic.config import Config
from typing import TextIO
from pystatic.manager import Manager
from pystatic.message import MessageBox


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
    parser.add_argument('--no-typeshed',
                        action='store_true',
                        help='disable typeshed files')
    parser.add_argument('--shell',
                        action='store_true',
                        help='run pystatic shell')
    parse_res = parser.parse_args()
    return parse_res


def cmdline_main(stdout: TextIO, stderr: TextIO):
    cmd_res = cmdline_parse()
    if not cmd_res.module:
        cmd_res.module = []

    config = Config(cmd_res)
    manager = Manager(config)

    if cmd_res.shell:
        pass
    elif cmd_res.stubgen:
        pass
    else:
        cmdline_mbox = MessageBox('cmdline')
        cmd_res.module = [os.path.realpath(path) for path in cmd_res.module]
        for mod in cmd_res.module:
            add_option = manager.add_check_file(mod)
            add_option.dump_to_box(cmdline_mbox)

        manager.preprocess()

        for err in cmdline_mbox.error:
            stdout.write(f'{err}\n')

        for mod in cmd_res.module:
            mbox = manager.get_mbox(mod)

            for err in mbox.error:
                stdout.write(f'{err}\n')
