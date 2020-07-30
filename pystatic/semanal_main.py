from .semanal import ClassCollector, TypeRecorder


def semanal_analyse(env, err, treenode):
    ClassCollector(env, err).accept(treenode)
    TypeRecorder(env, err).accept(treenode)
