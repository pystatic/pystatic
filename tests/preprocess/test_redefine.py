import sys
sys.path.extend(['.', '..'])

from ..util import get_manager_path, parse_file_error


def test_class_redefine():
    symid = 'preprocess.class_redefine'
    manager, path = get_manager_path({}, symid)
    manager.preprocess()

    true_msg_list = parse_file_error(path)
    mbox = manager.get_mbox_by_symid(symid)
    test_msg_list = mbox.to_message()
    assert len(true_msg_list) == len(test_msg_list)
    for true_msg, test_msg in zip(true_msg_list, test_msg_list):
        assert test_msg.lineno == true_msg.lineno
        assert test_msg.msg == true_msg.msg
