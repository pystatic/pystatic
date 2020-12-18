from typing import List

from pystatic.error.errorcode import ErrorCode, Sendable


class ErrorBox(object):
    def __init__(self, tag: str):
        self.tag = tag
        self.error: List[ErrorCode] = []

    def add_err(self, err: ErrorCode):
        self.error.append(err)

    def release(self, mailman: Sendable):
        for error in self.error:
            error.send_message(self, mailman)
        self.error = []

    def clear(self):
        self.error = []
