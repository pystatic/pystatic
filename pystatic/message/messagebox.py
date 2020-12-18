from typing import List

from pystatic.message.errorcode import Message
from pystatic.message.errorcode import ErrorCode


class MessageBox(object):
    def __init__(self, module_symid: str):
        self.module_symid = module_symid
        self.error: List[ErrorCode] = []

    def add_err(self, err: ErrorCode):
        self.error.append(err)

    def to_message(self):
        msg_list = []
        for err in self.error:
            node, msg = err.make()
            if node:
                msg_list.append(Message.from_node(node, msg))
        return sorted(msg_list)

    def clear(self):
        self.error = []
