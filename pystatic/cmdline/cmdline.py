import argparse
import os
from pystatic.config import Config
from pystatic.manager import Manager
from pystatic.message import MessageBox, Message
from pystatic.cmdline.shell import run_shell


def cmdline_parse():
    parser = argparse.ArgumentParser('python static type checker')
    parser.add_argument('module',
                        metavar='module',
                        nargs='*',
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
    parser.add_argument('--test-typeshed', action='store_true')
    parse_res = parser.parse_args()
    return parse_res


def cmdline_main():
    cmd_res = cmdline_parse()
    if not cmd_res.module:
        cmd_res.module = []

    config = Config(cmd_res)
    manager = Manager(config)

    if cmd_res.shell:
        run_shell(config)
    elif cmd_res.stubgen:
        pass
    else:
        cmdline_mbox = MessageBox('cmdline')
        cmd_res.module = [os.path.realpath(path) for path in cmd_res.module]
        if not cmd_res.module:
            print('please enter module path or package path')
            return

        for mod in cmd_res.module:
            add_result = manager.add_check_file(mod)
            add_result.dump_to_box(cmdline_mbox)

        manager.preprocess()
        manager.infer()

        # for err in cmdline_mbox.error:
        for err in cmdline_mbox.to_message():
            print(f'{err}')

        for mod in cmd_res.module:
            mbox = manager.get_mbox(mod)

            # for err in mbox.error:
            for err in mbox.to_message():
                print(f'{err}')
