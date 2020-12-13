import copy
from typing import Optional, List, TYPE_CHECKING
from pystatic.errorcode import *

if TYPE_CHECKING:
    from pystatic.typesys import TypeIns
    from pystatic.evalutil import ApplyArgs


class Arg(object):
    def __init__(self, name, ann: "TypeIns", default=None, valid=False):
        """
        valid: whether this argument has default value
        """
        self.name = name
        self.ann = ann
        self.default = default
        self.valid = valid

    def __str__(self):
        from pystatic.predefined import any_ins

        result = self.name
        if self.ann != any_ins:
            result += ": " + str(self.ann)
        if self.valid:
            result += " = ..."
        return result


class Argument(object):
    def __init__(self):
        self.posonlyargs: List[Arg] = []
        self.args: List[Arg] = []
        self.kwonlyargs: List[Arg] = []
        self.vararg: Optional[Arg] = None
        self.kwarg: Optional[Arg] = None

    def __str__(self):
        arg_list = [str(arg) for arg in self.posonlyargs + self.args]
        if self.vararg:
            arg_list.append(str(self.vararg))
        arg_list += [str(arg) for arg in self.kwonlyargs]
        if self.kwarg:
            arg_list.append(str(self.kwarg))

        return "(" + ", ".join(arg_list) + ")"


def copy_argument(argument: Argument):
    new_argument = Argument()
    new_argument.posonlyargs = copy.copy(argument.posonlyargs)
    new_argument.args = copy.copy(argument.args)
    new_argument.kwonlyargs = copy.copy(argument.kwonlyargs)
    new_argument.vararg = argument.vararg
    new_argument.kwarg = argument.kwarg
    return new_argument


def match_argument(
    argument: Argument, applyargs: "ApplyArgs", callnode: Optional[ast.AST]
) -> List[ErrorCode]:
    from pystatic.TypeCompatible.simpleType import type_consistent

    errorlist = []
    missing_args: List[str] = []
    too_more_arg = False

    def match_arg(arg: Arg, typeins: "TypeIns", node: ast.AST):
        if not type_consistent(arg.ann, typeins):
            errorlist.append(IncompatibleArgument(node, arg.name, arg.ann, typeins))

    i_apply_arg = 0
    len_apply_arg = len(applyargs.args)
    args = applyargs.args

    for arg in argument.posonlyargs:
        if i_apply_arg >= len_apply_arg:
            missing_args.append(arg.name)
        else:
            match_arg(arg, args[i_apply_arg].value, args[i_apply_arg].node)
            i_apply_arg += 1

    i_param_arg = 0
    len_param_arg = len(argument.args)
    param_args = argument.args
    while i_param_arg < len_param_arg:
        if i_apply_arg >= len_apply_arg:
            break
        else:
            match_arg(
                param_args[i_param_arg], args[i_apply_arg].value, args[i_apply_arg].node
            )
            i_apply_arg += 1
            i_param_arg += 1

    kwargs = applyargs.kwargs
    if i_param_arg >= len_param_arg:
        if i_apply_arg < len_apply_arg:
            if not argument.vararg:
                if not too_more_arg:
                    errorlist.append(TooMoreArgument(callnode))
                    too_more_arg = True
            else:
                # *args
                while i_apply_arg < len_apply_arg:
                    match_arg(
                        argument.vararg, args[i_apply_arg].value, args[i_apply_arg].node
                    )
                    i_apply_arg += 1
    else:
        assert i_apply_arg >= len_apply_arg
        while i_param_arg < len_param_arg:
            name = param_args[i_param_arg].name
            if name in kwargs:
                match_arg(
                    param_args[i_param_arg], kwargs[name].value, kwargs[name].node
                )
                kwargs.pop(name)
            else:
                missing_args.append(name)
            i_param_arg += 1

    for arg in argument.kwonlyargs:
        if arg.name in kwargs:
            target_ins = kwargs[arg.name]
            match_arg(arg, target_ins.value, target_ins.node)
            kwargs.pop(arg.name)
        else:
            missing_args.append(arg.name)

    if len(kwargs):
        if argument.kwarg:
            for apply_kwarg in kwargs.values():
                match_arg(argument.kwarg, apply_kwarg.value, apply_kwarg.node)
        else:
            if not too_more_arg:
                too_more_arg = True
                errorlist.append(TooMoreArgument(callnode))

    if missing_args:
        errorlist.append(TooFewArgument(callnode, missing_args))

    return errorlist
