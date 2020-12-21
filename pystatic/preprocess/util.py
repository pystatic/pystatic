import ast
from typing import Optional, TYPE_CHECKING, List
from pystatic.infer.infer_expr import SupportGetAttribute
from pystatic.typesys import TypeIns, TypeType
from pystatic.predefined import TypeModuleIns, TypePackageIns, TypeClassTemp
from pystatic.visitor import NoGenVisitor, VisitorMethodNotFound
from pystatic.result import Result
from pystatic.symtable import ImportNode, SymTable
from pystatic.symid import SymId, rel2abssymid, symid_parent, absolute_symidlist
from pystatic.preprocess.prepinfo import prep_impt, PrepInfo

if TYPE_CHECKING:
    from pystatic.manager import Manager


def omit_inst_typetype(
    node: ast.AST, consultant: SupportGetAttribute, allow_tuple: bool
) -> Optional[TypeType]:
    """Get the typetype a node represents while omitting instantiate args

    @param allow_tuple: allow analyse inside tuple node or not
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
    def accept(self, node: ast.AST, consultant: SupportGetAttribute, allow_tuple: bool):
        self.consultant = consultant
        self.allow_tuple = allow_tuple
        return self.visit(node)

    def visit_Name(self, node: ast.Name) -> Optional[TypeIns]:
        name_result = self.consultant.getattribute(node.id, node)
        assert isinstance(name_result, Result)
        res = name_result.value
        if not isinstance(res, TypeType):
            return None
        return res

    def visit_Attribute(self, node: ast.Attribute) -> Optional[TypeIns]:
        res = self.visit(node.value)
        if not res:
            return None
        assert isinstance(res, TypeType)
        attr_result = res.getattribute(node.attr, node)
        attr_res = attr_result.value
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


def analyse_import_stmt(
    prepinfo: "PrepInfo", node: ImportNode, symid: SymId
) -> List[prep_impt]:
    """Extract import information stored in import ast node."""
    info_list: List[prep_impt] = []
    pkg_symid = symid_parent(symid)
    if isinstance(node, ast.Import):
        for alias in node.names:
            module_symid = alias.name
            as_name = alias.asname or module_symid
            info_list.append(prep_impt(module_symid, "", as_name, prepinfo, node))

    elif isinstance(node, ast.ImportFrom):
        imp_name = "." * node.level
        imp_name += node.module or ""
        module_symid = rel2abssymid(pkg_symid, imp_name)
        for alias in node.names:
            attr_name = alias.name
            as_name = alias.asname or attr_name
            if (
                symid.endswith(".__init__") and module_symid == symid[:-9]
            ):  # 9 == len('.__init__')
                # special case: __init__.py import a module under the same package
                info_list.append(
                    prep_impt(
                        module_symid + "." + attr_name, "", as_name, prepinfo, node
                    )
                )
            else:
                info_list.append(
                    prep_impt(module_symid, attr_name, as_name, prepinfo, node)
                )

    else:
        raise TypeError("node doesn't stand for an import statement")

    return info_list


def add_baseclass(temp: TypeClassTemp, basecls: "TypeIns"):
    if basecls not in temp.baseclass:
        temp.baseclass.append(basecls)
