import copy
from pystatic.typesys import TypeAnyTemp, TypeIns, any_ins
from typing import Optional, List


class Arg(object):
    def __init__(self,
                 name,
                 ann: TypeIns = any_ins,
                 default=None,
                 valid=False):
        """
        valid: whether this argument has default value
        """
        self.name = name
        self.ann = ann
        self.default = default
        self.valid = valid

    def __str__(self):
        result = self.name
        if self.ann != any_ins:
            result += ': ' + str(self.ann)
        if self.valid:
            result += ' = ...'
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

        return '(' + ', '.join(arg_list) + ')'


def copy_argument(argument: Argument):
    new_argument = Argument()
    new_argument.posonlyargs = copy.copy(argument.posonlyargs)
    new_argument.args = copy.copy(argument.args)
    new_argument.kwonlyargs = copy.copy(argument.kwonlyargs)
    new_argument.vararg = argument.vararg
    new_argument.kwarg = argument.kwarg
    return new_argument
