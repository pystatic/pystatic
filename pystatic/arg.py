import copy
import itertools
from pystatic.error.errorcode import *

if TYPE_CHECKING:
    from pystatic.typesys import TypeIns
    from pystatic.infer.util import ApplyArgs


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

        # vararg and kwarg's star is not store in the name
        self.vararg: Optional[Arg] = None
        self.kwarg: Optional[Arg] = None

    def get_arg_namelist(self) -> List[str]:
        """Get arguments' name and keep their order"""
        res = []
        for arg in itertools.chain(self.posonlyargs, self.args):
            res.append(arg.name)
        if self.vararg:
            res.append(self.vararg.name)
        for arg in self.kwonlyargs:
            res.append(arg.name)
        if self.kwarg:
            res.append(self.kwarg.name)
        return res

    def __str__(self):
        arg_list = [str(arg) for arg in self.posonlyargs + self.args]
        if self.vararg:
            arg_list.append("*" + str(self.vararg))
        arg_list += [str(arg) for arg in self.kwonlyargs]
        if self.kwarg:
            arg_list.append("**" + str(self.kwarg))

        return "(" + ", ".join(arg_list) + ")"


def copy_argument(argument: Argument):
    new_argument = Argument()
    new_argument.posonlyargs = copy.copy(argument.posonlyargs)
    new_argument.args = copy.copy(argument.args)
    new_argument.kwonlyargs = copy.copy(argument.kwonlyargs)
    new_argument.vararg = argument.vararg
    new_argument.kwarg = argument.kwarg
    return new_argument


def match_argument(argument: Argument, applyargs: "ApplyArgs",
                   callnode: Optional[ast.AST]) -> List[ErrorCode]:
    from pystatic.consistent import is_consistent

    errorlist = []
    missing_args: List[str] = []
    too_more_arg = False

    def match_arg(arg: Arg, name: str, typeins: "TypeIns", node: ast.AST):
        if not is_consistent(arg.ann, typeins):
            errorlist.append(IncompatibleArgument(node, name, arg.ann,
                                                  typeins))

    i_apply_arg = 0  # index of args scanned in applyargs argument list
    len_apply_arg = len(applyargs.args)
    args = applyargs.args  # args part of applyargs argument list

    for arg in argument.posonlyargs:
        if i_apply_arg >= len_apply_arg:
            missing_args.append(arg.name)
        else:
            # match posonly arguments
            match_arg(arg, arg.name, args[i_apply_arg].value,
                      args[i_apply_arg].node)
            i_apply_arg += 1

    i_param_arg = 0  # index of args scanned in parameter argument list
    len_param_arg = len(argument.args)
    param_args = argument.args  # args part of parameter argument list
    while i_param_arg < len_param_arg:
        if i_apply_arg >= len_apply_arg:
            break
        else:
            # match arg
            match_arg(
                param_args[i_param_arg],
                param_args[i_param_arg].name,
                args[i_apply_arg].value,
                args[i_apply_arg].node,
            )
            i_apply_arg += 1
            i_param_arg += 1

    kwargs = applyargs.kwargs
    if i_param_arg >= len_param_arg:
        # args part of parameter argument list are all matched
        if i_apply_arg < len_apply_arg:
            # use args in applyargs to match keyword argument of parameter
            if not argument.vararg:
                if not too_more_arg:
                    errorlist.append(TooMoreArgument(callnode))
                    too_more_arg = True
            else:
                # match *args
                while i_apply_arg < len_apply_arg:
                    match_arg(
                        argument.vararg,
                        "*" + argument.vararg.name,
                        args[i_apply_arg].value,
                        args[i_apply_arg].node,
                    )
                    i_apply_arg += 1
    else:
        # args part of applyargs are all matched
        assert i_apply_arg >= len_apply_arg
        while i_param_arg < len_param_arg:
            # match keyword argument in applyargs with args of parameter args
            cur_argname = param_args[i_param_arg].name
            if cur_argname in kwargs:
                match_arg(
                    param_args[i_param_arg],
                    cur_argname,
                    kwargs[cur_argname].value,
                    kwargs[cur_argname].node,
                )
                kwargs.pop(cur_argname)
            else:
                missing_args.append(cur_argname)
            i_param_arg += 1

    for arg in argument.kwonlyargs:
        if arg.name in kwargs:
            # match kwonlyargs of parameter
            target_ins = kwargs[arg.name]
            match_arg(arg, arg.name, target_ins.value, target_ins.node)
            kwargs.pop(arg.name)
        else:
            missing_args.append(arg.name)

    if len(kwargs):
        if argument.kwarg:
            for apply_kwarg in kwargs.values():
                # match **kwargs
                match_arg(
                    argument.kwarg,
                    "**" + argument.kwarg.name,
                    apply_kwarg.value,
                    apply_kwarg.node,
                )
        else:
            if not too_more_arg:
                too_more_arg = True
                errorlist.append(TooMoreArgument(callnode))

    if missing_args:
        errorlist.append(TooFewArgument(callnode, missing_args))

    return errorlist
