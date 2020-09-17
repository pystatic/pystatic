from typing import Optional, Union, Set
from pystatic.typesys import TypeIns, TypeType
from pystatic.symtable import Deferred, SymTable, DeferredElement, Entry


def eval_defer(defer: Deferred, symtable: SymTable) -> Optional['TypeType']:
    assert len(defer.elements) > 0
    return _eval_defer(defer.get(0), symtable, symtable)


def _eval_defer(defer: DeferredElement, topitem: Union[TypeIns, SymTable],
                symtable: SymTable) -> Optional['TypeType']:
    tpins = topitem.getattr(defer.name)
    if tpins:
        assert isinstance(tpins, TypeType)
        bindlist = []
        for bind in defer.bindlist.binding:
            tmp: Optional[Union[list, TypeIns]] = None
            if isinstance(bind, list):
                tmp = []
                for subbind in bind:
                    tmp.append(eval_defer(subbind, symtable))
            else:
                tmp = eval_defer(bind, symtable)
            if tmp is None:
                bindlist.append(tmp)
            else:
                return None
        res, _ = tpins.getitem(bindlist)  # TODO: check consistence here
        return res
    return None


def remove_defer(symtable: SymTable) -> bool:
    defer_entries: Set[Entry] = set()
    for entry in symtable.local.values():
        if isinstance(entry.get_real_type(), Deferred):
            defer_entries.add(entry)

    progress = True
    while progress:
        progress = False
        tmp_defer = set()
        for entry in defer_entries:
            res = entry.get_real_type()
            if isinstance(res, Deferred):
                tpins = eval_defer(res, symtable)
                if tpins:
                    progress = True
                    entry.tp = tpins
            else:
                tmp_defer.add(entry)
        defer_entries = tmp_defer

    return not defer_entries
