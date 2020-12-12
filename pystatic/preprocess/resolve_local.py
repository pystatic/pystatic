import ast
from pystatic.predefined import TypeVarTemp
from pystatic.exprparse import eval_expr
from pystatic.preprocess.resolve_spt import resolve_typealias
from pystatic.preprocess.util import omit_inst_typetype
from pystatic.preprocess.resolve_util import eval_preptype
from pystatic.preprocess.prepinfo import *


def judge_typevar(prepinfo: "PrepInfo", node: AssignNode):
    def get_name(node: ast.AST) -> Optional[str]:
        if isinstance(node, ast.Name):
            return node.id
        return None

    value_node = node.value
    if isinstance(value_node, ast.Call):
        f_ins = eval_expr(value_node.func, prepinfo).value
        if isinstance(f_ins, TypeType) and isinstance(f_ins.temp, TypeVarTemp):
            if isinstance(node, ast.AnnAssign):
                typevar_name = get_name(node)
                assert typevar_name  # TODO: error
            elif isinstance(node, ast.Assign):
                assert node.targets[0]  # TODO: error
                typevar_name = get_name(node.targets[0])
                assert typevar_name  # TODO: error
            else:
                raise TypeError()
            typevar = TypeVarIns(typevar_name)
            prepinfo.add_typevar_def(typevar_name, typevar, node)
            return typevar
    return None


def judge_typealias(prepinfo: "PrepInfo", node: AssignNode) -> Optional[TypeAlias]:
    if isinstance(node, ast.AnnAssign):
        # assignment with type annotation is not a type alias.
        return None

    if node.value:
        typetype = omit_inst_typetype(node.value, prepinfo, False)
        if typetype:
            if isinstance(typetype, tuple):
                raise NotImplementedError()
            else:
                if len(node.targets) != 1:
                    return None
                else:
                    target = node.targets[0]

                if isinstance(target, ast.Name):
                    typealias = TypeAlias(target.id, typetype)
                    prepinfo.add_type_alias(target.id, typealias, node)
                    return typealias
                else:
                    raise NotImplementedError()
    return None


def resolve_local(local: "prep_local", shallow: bool):
    """Resolve local symbols' TypeIns

    :param shallow: if set True, local's current stage must be LOCAL_NORMAL.
    This function will judge the type of the local symbol(typevar or typealias)
    and won't visit node inside subscript node.
    """
    assert isinstance(local, prep_local)
    prepinfo = local.def_prepinfo

    if shallow:
        assert local.stage == LOCAL_NORMAL
        if (typevar := judge_typevar(prepinfo, local.defnode)) :
            local.value = typevar
            local.type = LOCAL_TYPEVAR
            return
        elif (typealias := judge_typealias(prepinfo, local.defnode)) :
            local.value = typealias
            local.type = LOCAL_TYPEALIAS
            return

    assert not local.type == LOCAL_TYPEVAR
    if local.type == LOCAL_TYPEALIAS:
        resolve_typealias(local)
        return

    typenode = local.typenode
    if not typenode:
        local.stage = PREP_COMPLETE
        return

    eval_res = eval_preptype(typenode, local.def_prepinfo, True, shallow)
    typeins = eval_res.option_ins.value
    if isinstance(typeins, TypeType):
        local.value = typeins.get_default_ins()
    else:
        local.value = typeins
    if shallow and eval_res.generic:
        local.stage = PREP_NULL
    else:
        local.stage = PREP_COMPLETE

    if not shallow:
        eval_res.option_ins.dump_to_box(local.def_prepinfo.mbox)
