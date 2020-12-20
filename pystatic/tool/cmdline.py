import argparse
import os
from os.path import isdir
from typing import Optional, List
from pystatic.config import Config
from pystatic.manager import Manager
from pystatic.error.errorbox import ErrorBox
import pystatic.tool.stubgen as stubgen
import pystatic.tool.shell as shell
import pystatic.tool.instaviz.web as web


def cmdline_parse():
    parser = argparse.ArgumentParser("python static type checker")
    parser.add_argument(
        "module", metavar="module", nargs="*", help="module path", type=str
    )
    parser.add_argument(
        "-p",
        "--package",
        metavar="package path",
        help="package path",
        type=str,
    )
    parser.add_argument("--stubgen", action="store_true", help="generate stub files")
    parser.add_argument(
        "--no-typeshed", action="store_true", help="disable typeshed files"
    )
    parser.add_argument("--shell", action="store_true", help="run pystatic shell")
    parser.add_argument("--web", action="store_true", help="web view")
    parser.add_argument("--test-typeshed", action="store_true")
    parse_res = parser.parse_args()
    return parse_res


def cmdline_main():
    cmd_res = cmdline_parse()

    if not cmd_res.module:
        cmd_res.module = []
    cmd_res.module = [os.path.realpath(path) for path in cmd_res.module]

    if cmd_res.package:
        cmd_res.package = os.path.realpath(cmd_res.package)
        package_paths = _search_modules_under_package(cmd_res.package)
        if package_paths:
            cmd_res.module.extend(package_paths)
        else:
            print(f"{cmd_res.package} may not be a package.")
            return

    config = Config(cmd_res)
    cmd_res.module = list(set(cmd_res.module))  # remove duplicates

    if cmd_res.shell:
        shell.run(config, cmd_res.module)
    elif cmd_res.stubgen:
        pass
    elif cmd_res.web:
        web.run(config, cmd_res.module)
    else:
        manager = Manager(config)
        if not cmd_res.module:
            print("please enter module path or package path")
            return

        cmdline_errbox = ErrorBox("__CMDLINE__")
        for mod in cmd_res.module:
            add_result = manager.add_check_file(mod)
            add_result.dump_to_box(cmdline_errbox)

        manager.preprocess()
        manager.infer()

        cmdline_errbox.release(manager)
        for mod in cmd_res.module:
            msg_list = manager.take_messages(mod)
            for msg in msg_list:
                output_info = " ".join([mod, str(msg)])
                print(output_info)

        # symid_errors = manager.take_all_messages()

        # for symid, err_list in symid_errors.items():
        #     for err in err_list:
        #         output_info = " ".join([symid, str(err)])
        #         print(output_info)


def _search_modules_under_package(package_abspath) -> Optional[List[str]]:
    if not isdir(package_abspath):
        return None

    files = os.listdir(package_abspath)
    is_package = False
    for cur_file in files:
        if cur_file == "__init__.py" and os.path.isfile(
            os.path.join(package_abspath, cur_file)
        ):
            is_package = True
            break

    if not is_package:
        return None

    result = []
    for (root, _, files) in os.walk(package_abspath):
        for file in files:
            if file.endswith(".py"):
                file_abspath = os.path.realpath(os.path.join(root, file))
                result.append(file_abspath)

    return result
