import ast
import os
import time

USER_DEFINE = 'user-defined'
THIRDPARTY_DEFINE = 'third-party define'
BUILTIN_DEFINE = 'built-in define'


class ImportModule:
    def __init__(self, modulename, filepath, classdef: list, variates: list,
                 fundef: list, last_visit_time):
        self.filepath = filepath
        self.classdef = classdef
        self.variates = variates
        self.fundef = fundef
        self.last_visit_time = last_visit_time

    def get_module_content(self):
        last_modify_time = time.ctime(os.path.getmtime(self.filepath))
        if last_modify_time > self.last_visit_time:
            return False  # need to refresh this module's name
        else:
            return True  # can read content directly

    def modify_last_visit_time(self, last_visit_time):
        self.last_visit_time = last_visit_time

    def get_classdef(self):
        return self.classdef

    def get_variates(self):
        return self.variates

    def get_fundef(self):
        return self.fundef


class ImportContent:
    def __init__(self,
                 modulename,
                 asname,
                 filepath,
                 typemodule=USER_DEFINE,
                 hascontent=False,
                 content=[]):
        self.__modulename = modulename
        self.__asname = asname
        self.__filepath = filepath
        self.__typemodule = typemodule
        self.get_file_content()
        self.hascontent = hascontent
        self.__content = content  # used to store types and variates' names
        self.__source = ' '
        self.get_file_content()

    def get_file_content(self):
        if self.__typemodule == BUILTIN_DEFINE:
            return
        else:
            self.__source = open(file=self.__filepath,
                                 mode="r+",
                                 encoding="UTF-8").read()
            self.__tree = ast.parse(self.__source, type_comments=True)
        return

    def get_ast_tree(self):
        return self.__tree

    def get_content(self):
        return self.__content

    def get_source(self):
        return self.__source
