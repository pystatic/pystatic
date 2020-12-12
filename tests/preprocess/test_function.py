from logging import error
import sys
sys.path.extend(['.', '..'])

from ..util import error_assert

def test_simple_function():
    error_assert('preprocess.prep_simple_function')
