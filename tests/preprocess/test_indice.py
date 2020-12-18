import sys

sys.path.extend([".", ".."])

from ..util import *


def test_indice_error():
    error_assert("preprocess.prep_indice_error")
