import sys

sys.path.extend([".", ".."])

from ..util import error_assert


def test_redefine():
    error_assert("preprocess.prep_redefine", False)
