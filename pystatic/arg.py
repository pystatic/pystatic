from pystatic.typesys import BaseType, TypeAny, any_type
from typing import Optional, List


class Arg(object):
    def __init__(self,
                 name,
                 ann: BaseType = any_type,
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
        if not isinstance(self.ann, TypeAny):
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
            arg_list.append('*' + str(self.vararg))
        arg_list += [str(arg) for arg in self.kwonlyargs]
        if self.kwarg:
            arg_list.append('**' + str(self.kwarg))

        return '(' + ', '.join(arg_list) + ')'
