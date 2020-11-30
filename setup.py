import os
import glob
from setuptools import setup, find_packages


def get_typeshed(directory):
    alldir = [root for root, _, _ in os.walk(directory)]
    result = []
    for dir in alldir:
        files = []
        for pat in ['*.pyi', '*.py']:
            files += glob.glob(os.path.join(dir, pat))
        if not files:
            continue
        result.extend([os.path.relpath(f, dir) for f in files])
    return result


package_data = get_typeshed(os.path.join('pystatic', 'faketypeshed'))
package_data += get_typeshed(os.path.join('pystatic', 'typeshed'))

setup(name='pystatic',
      packages=['pystatic'],
      package_data={'pystatic': package_data})
