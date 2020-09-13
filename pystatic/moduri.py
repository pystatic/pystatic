import os
from typing import List

ModUri = str


def count_uri_head_dots(uri: ModUri) -> int:
    """find out how many dots at the begining of a uri"""
    i = 0
    while len(uri) > i and uri[i] == '.':
        i += 1
    return i


def uri2list(uri: ModUri) -> List[str]:
    return [item for item in uri.split('.') if item != '']


def list2uri(urilist: List[str]) -> ModUri:
    return '.'.join(urilist)


def uri_parent(uri: ModUri) -> ModUri:
    """Return the parent uri(a.b.c -> a.b, a -> ''), uri should be absolute"""
    return '.'.join(uri2list(uri)[:-1])


def uri_last(uri: ModUri) -> str:
    """Return the last(a.b.c -> c, a -> a)"""
    if not uri:
        return ''
    return uri2list(uri)[-1]


def absolute_urilist(uri: ModUri, cur_uri: ModUri) -> List[str]:
    i = count_uri_head_dots(uri)
    if i == 0:  # the uri itself is an absolute uri
        return uri2list(uri)
    else:
        rel_uri = uri2list(uri[i:])
        if i == 1:
            return uri2list(cur_uri) + rel_uri
        else:
            return uri2list(cur_uri)[:-(i // 2)] + rel_uri


def relpath2uri(prefix_path: str, src_path: str) -> ModUri:
    """Generate uri from the path

    Example:
        If prefix_path is '/a/b/c' and src_path is /a/b/c/d/e.py
        then return 'd.e'
    """
    commonpath = os.path.commonpath([prefix_path, src_path])
    relpath = os.path.relpath(src_path, commonpath)
    if relpath.endswith('.py'):
        relpath = relpath[:-3]
    elif relpath.endswith('.pyi'):
        relpath = relpath[:-4]
    return '.'.join(relpath.split(os.path.sep))


def rel2absuri(cur_uri: ModUri, rel_uri: ModUri):
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
