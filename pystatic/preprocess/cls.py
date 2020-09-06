import ast
from typing import Tuple, List
from collections import OrderedDict
from pystatic.env import Environment
from pystatic.typesys import TypeGenericTemp, TypeIns, TypeVar, TypeType, TypeList
from pystatic.util import ParseException
from pystatic.preprocess.annotation import (parse_annotation,
                                            get_typevar_from_ann)


def analyse_cls_def(node: ast.ClassDef,
                    env: Environment) -> Tuple[List[TypeType], TypeList]:
    met_generic = False
    typevar_set: 'OrderedDict[str, TypeVar]' = OrderedDict()
    normal_set: 'OrderedDict[str, TypeVar]' = OrderedDict()
    generic_node = None
    base_list: List[TypeType] = []
    for base in node.bases:
        try:
            base_tp = parse_annotation(base, env, False)
            if base_tp:
                base_list.append(base_tp)
                if isinstance(base_tp.temp, TypeGenericTemp):
                    if met_generic:
                        env.add_err(base, f'only one Generic is allowed')
                    else:
                        met_generic = True
                        get_typevar_from_ann(base, env, normal_set)
                        generic_node = base
                else:
                    get_typevar_from_ann(base, env, typevar_set)
            else:
                env.add_err(base, f'invalid base class')
        except ParseException as e:
            env.add_err(e.node, e.msg or f'invalid base class')

    if met_generic:
        assert generic_node
        missing_typevar = []
        for varname in typevar_set:
            if varname not in normal_set:
                missing_typevar.append(varname)

        if len(missing_typevar) > 0:
            env.add_err(generic_node,
                        ','.join(missing_typevar) + ' should in Generic')
        normal_set.update(typevar_set)
        return base_list, list(normal_set.values())
    else:
        return base_list, list(typevar_set.values())
