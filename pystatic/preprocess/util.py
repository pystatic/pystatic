import ast
from typing import Optional, TYPE_CHECKING, List
from pystatic.exprparse import SupportGetAttribute
from pystatic.typesys import TypeIns, TypeType
from pystatic.predefined import (TypeModuleIns, TypePackageIns, TypeClassTemp)
from pystatic.visitor import NoGenVisitor, VisitorMethodNotFound
from pystatic.option import Option
from pystatic.symtable import ImportNode, SymTable
from pystatic.symid import SymId, rel2abssymid, symid_parent, absolute_symidlist
from pystatic.preprocess.prepinfo import prep_impt, PrepInfo

if TYPE_CHECKING:
    from pystatic.manager import Manager


def omit_inst_typetype(node: ast.AST, consultant: SupportGetAttribute,
                       allow_tuple: bool) -> Optional[TypeType]:
    """Get typetype a node represents while omitting instantiate args

    :param allow_tuple: allow analyse inside tuple node or not
    """
    try:
        res = typetype_getter.accept(node, consultant, allow_tuple)
        if not res:
            return None
        assert isinstance(res, TypeType)
        return res
    except VisitorMethodNotFound:
        return None


class TypeTypeGetter(NoGenVisitor):
    def accept(self, node: ast.AST, consultant: SupportGetAttribute,
               allow_tuple: bool):
        self.consultant = consultant
        self.allow_tuple = allow_tuple
        return self.visit(node)

    def visit_Name(self, node: ast.Name) -> Optional[TypeIns]:
        name_option = self.consultant.getattribute(node.id, node)
        assert isinstance(name_option, Option)
        res = name_option.value
        if not isinstance(res, TypeType):
            return None
        return res

    def visit_Attribute(self, node: ast.Attribute) -> Optional[TypeIns]:
        res = self.visit(node.value)
        if not res:
            return None
        assert isinstance(res, TypeType)
        attr_option = res.getattribute(node.attr, node)
        attr_res = attr_option.value
        if not isinstance(attr_res, TypeType):
            return None
        return attr_res

    def visit_Subscript(self, node: ast.Subscript) -> Optional[TypeIns]:
        left_ins = self.visit(node.value)
        if not left_ins:
            return None
        assert isinstance(left_ins, TypeType)

        return left_ins

    def visit_Tuple(self, node: ast.Tuple):
        if self.allow_tuple:
            typetype_list = []
            for subnode in node.elts:
                cur_typetype = self.visit(subnode)
                if not cur_typetype:
                    return None
                typetype_list.append(cur_typetype)
            return tuple(typetype_list)

        else:
            return None


typetype_getter = TypeTypeGetter()


def analyse_import_stmt(prepinfo: 'PrepInfo', node: ImportNode,
                        symid: SymId) -> List[prep_impt]:
    """Extract import information stored in import ast node."""
    info_list: List[prep_impt] = []
    pkg_symid = symid_parent(symid)
    if isinstance(node, ast.Import):
        for alias in node.names:
            module_symid = alias.name
            as_name = alias.asname or module_symid
            info_list.append(
                prep_impt(module_symid, '', as_name, prepinfo, node))

    elif isinstance(node, ast.ImportFrom):
        imp_name = '.' * node.level
        imp_name += node.module or ''
        module_symid = rel2abssymid(pkg_symid, imp_name)
        imported = []
        for alias in node.names:
            attr_name = alias.name
            as_name = alias.asname or attr_name
            imported.append((as_name, attr_name))
            info_list.append(
                prep_impt(module_symid, attr_name, as_name, prepinfo, node))

    else:
        raise TypeError("node doesn't stand for an import statement")

    return info_list


def update_symtable_import_cache(symtable: 'SymTable', entry: 'prep_impt',
                                 manager: 'Manager') -> Optional[TypeIns]:
    symid = entry.symid

    symidlist = absolute_symidlist(symtable.glob_symid, symid)
    if not symidlist:
        return None

    cache = symtable.import_cache

    # get the initial module ins or package ins
    cur_symid = symidlist[0]
    cur_ins = cache.get_module_ins(cur_symid)

    if not cur_ins:
        cur_ins = manager.get_module_ins(symidlist[0])
        if not cur_ins:
            return None
        cache.set_moduleins(cur_symid, cur_ins)

    assert isinstance(cur_ins, TypeModuleIns)
    for i in range(1, len(symidlist)):
        if not isinstance(cur_ins, TypePackageIns):
            return None

        cur_symid += f'.{symidlist[i]}'
        if symidlist[i] not in cur_ins.submodule:
            module_ins = manager.get_module_ins(cur_symid)
            if not module_ins:
                return None

            # FIXME: fix me after modify TypePackageIns
            assert isinstance(module_ins, TypeModuleIns)
            if isinstance(module_ins, TypePackageIns):
                cur_ins.add_submodule(symidlist[i], module_ins)
            else:
                if i != len(symidlist) - 1:
                    return None
                cur_ins.add_submodule(symidlist[i], module_ins)
                return module_ins

        cur_ins = cur_ins.submodule[symidlist[i]]

    assert cur_symid == entry.symid

    # If the source is a package then another module may be imported.
    # Example:
    # from fruit import apple
    # fruit is a package and apple is a module so pystatic need to add apple
    # to fruit's submodule list
    if isinstance(cur_ins, TypePackageIns):
        if not entry.is_import_module():
            cur_symid += f'.{entry.origin_name}'
            module_ins = manager.get_module_ins(cur_symid)

            if module_ins:
                cur_ins.add_submodule(entry.origin_name, module_ins)
    return cur_ins


def add_baseclass(temp: TypeClassTemp, basecls: 'TypeIns'):
    if basecls not in temp.baseclass:
        temp.baseclass.append(basecls)
