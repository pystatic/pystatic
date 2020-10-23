import os
from typing import List

SymId = str


def count_symid_head_dots(symid: SymId) -> int:
    """Find out how many dots at the begining of a symid"""
    i = 0
    while len(symid) > i and symid[i] == '.':
        i += 1
    return i


def symid2list(symid: SymId) -> List[str]:
    """Split an symid to a list.

    Example:
    - 'A.B.C' -> ['A', 'B', 'C']
    """
    return [item for item in symid.split('.') if item != '']


def list2symid(symidlist: List[str]) -> SymId:
    """Join a list to create a symid.

    Example:
    - ['A', 'B'] -> 'A.B'
    """
    return '.'.join(symidlist)


def symid_parent(symid: SymId) -> SymId:
    """Return parent symid.

    symid:
        an absolute symid.

    Example:
    - a.b.c -> a.b
    - a -> ''

    """
    return '.'.join(symid2list(symid)[:-1])


def symid_last(symid: SymId) -> str:
    """Return the last name.

    Example:
    - a.b.c -> c
    - a -> a
    """
    if not symid:
        return ''
    return symid2list(symid)[-1]


def absolute_symidlist(cur_symid: SymId, symid: SymId) -> List[str]:
    """Get the absolute symid and convert it to a list.

    cur_symid:
        current symid.

    symid:
        relative symid to current symid.

    Example:
    - ('..', 'a.b.c') -> ['a', 'b']
    - ('.', 'a.b') -> ['a', 'b']
    """

    i = count_symid_head_dots(symid)
    if i == 0:  # the symid itself is an absolute symid
        return symid2list(symid)
    else:
        rel_symid = symid2list(symid[i:])
        if i == 1:
            return symid2list(cur_symid) + rel_symid
        else:
            return symid2list(cur_symid)[:-(i // 2)] + rel_symid


def relpath2symid(prefix_path: str, src_path: str) -> SymId:
    """Generate symid from the path.

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


def rel2abssymid(cur_symid: SymId, rel_symid: SymId):
    """Convert a relative symid to a absolute symid.

    Example:
    - ('a.b.c', '..d') -> 'a.b.d'
    """
    i = count_symid_head_dots(rel_symid)
    if i == 0:
        return rel_symid
    else:
        cur_symidlist = symid2list(cur_symid)
        rel_symidlist = symid2list(rel_symid[i:])
        if i != 1:
            cur_symidlist = cur_symidlist[:-(i // 2)]
        cur_symidlist.extend(rel_symidlist)
        return list2symid(cur_symidlist)
