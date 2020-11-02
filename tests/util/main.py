from tests.util.tool import parseprint
import os


# print(list(map(f, aa)))

fd = open("../test_cmp.py")
text = fd.read()

parseprint(text)
