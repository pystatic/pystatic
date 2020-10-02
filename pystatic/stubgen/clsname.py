from pystatic.typesys import TypeTemp
from pystatic.uri import uri2list


class Node:
    def __init__(self, uri: str):
        self.uri = uri
        self.suburi = {}
        self.alias = None

    def set_alias(self, alias: str):
        self.alias = alias


class NameTree:
    def __init__(self, module_uri: str):
        self.root = Node('')
        self.module_uri = module_uri

    def ask(self, temp: TypeTemp) -> str:
        module_uri = temp.module_uri
        uri = temp.name

        if module_uri == self.module_uri or module_uri == 'builtins':
            return uri

        urilist = uri2list(module_uri) + uri2list(uri)
        cur_node = self.root
        namelist = []
        for subname in urilist:
            if subname in cur_node.suburi:
                cur_node = cur_node.suburi[subname]
                if cur_node.alias:
                    namelist = [cur_node.alias]
                else:
                    namelist.append(subname)
            else:
                return '.'.join(urilist)
        return '.'.join(namelist)

    def add_import(self, module_uri: str, uri: str, asname: str):
        urilist = uri2list(module_uri) + uri2list(uri)
        cur_node = self.root

        for subname in urilist:
            if not subname:
                continue
            if subname in cur_node.suburi:
                cur_node = cur_node.suburi[subname]
            else:
                cur_node.suburi[subname] = Node(subname)

        if asname:
            cur_node.alias = asname
