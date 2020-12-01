import sys
sys.path.extend(['.', '..'])

from ..util import *


def test_indice_error():
    symid = 'preprocess.prep_indice_error'
    manager, path = get_manager_path({}, symid)
    manager.preprocess()

    true_msg_list = parse_file_error(path)
    mbox = manager.get_mbox_by_symid(symid)
    check_error_msg(mbox, true_msg_list)
