import os
from typing import List

Uri = str


def count_uri_head_dots(uri: Uri) -> int:
    """Find out how many dots at the begining of a uri"""
    i = 0
    while len(uri) > i and uri[i] == '.':
        i += 1
    return i


def uri2list(uri: Uri) -> List[str]:
    """Split an uri to a list.

    Example:
    - 'A.B.C' -> ['A', 'B', 'C']
    """
    return [item for item in uri.split('.') if item != '']


def list2uri(urilist: List[str]) -> Uri:
    """Join a list to create a uri.
    
    Example:
    - ['A', 'B'] -> 'A.B'
    """
    return '.'.join(urilist)


def uri_parent(uri: Uri) -> Uri:
    """Return parent uri.

    :param uri: an absolute uri.

    Example:
    - a.b.c -> a.b
    - a -> ''

    """
    return '.'.join(uri2list(uri)[:-1])


def uri_last(uri: Uri) -> str:
    """Return the last name.

    Example:
    - a.b.c -> c
    - a -> a
    """
    if not uri:
        return ''
    return uri2list(uri)[-1]


def absolute_urilist(cur_uri: Uri, uri: Uri) -> List[str]:
    """Get the absolute uri and convert it to a list.
    
    :param cur_uri: current uri
    :param uri: relative uri to current uri

    Example:
    - ('..', 'a.b.c') -> ['a', 'b']
    - ('.', 'a.b') -> ['a', 'b']
    """

    i = count_uri_head_dots(uri)
    if i == 0:  # the uri itself is an absolute uri
        return uri2list(uri)
    else:
        rel_uri = uri2list(uri[i:])
        if i == 1:
            return uri2list(cur_uri) + rel_uri
        else:
            return uri2list(cur_uri)[:-(i // 2)] + rel_uri


def relpath2uri(prefix_path: str, src_path: str) -> Uri:
    """Generate uri from the path.

    Example:
    - ('/a/b/c', '/a/b/c/d/e.py') -> 'd.e'
    """
    commonpath = os.path.commonpath([prefix_path, src_path])
    relpath = os.path.relpath(src_path, commonpath)
    if relpath.endswith('.py'):
        relpath = relpath[:-3]
    elif relpath.endswith('.pyi'):
        relpath = relpath[:-4]
    return '.'.join(relpath.split(os.path.sep))


def rel2absuri(cur_uri: Uri, rel_uri: Uri):
    """Convert a relative uri to a absolute uri.

    Example:
    - ('a.b.c', '..d') -> 'a.b.d'
    """
    i = count_uri_head_dots(rel_uri)
    if i == 0:
        return rel_uri
    else:
        cur_urilist = uri2list(cur_uri)
        rel_urilist = uri2list(rel_uri[i:])
        if i != 1:
            cur_urilist = cur_urilist[:-(i // 2)]
        cur_urilist.extend(rel_urilist)
        return list2uri(cur_urilist)
