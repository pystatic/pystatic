from typing import Optional, Tuple
from pystatic.error.level import Level
from pystatic.error.position import Position


class Message:
    __slots__ = ["level", "msg"]

    def __init__(self, level: Level, msg: str) -> None:
        self.level = level
        self.msg = msg

    def get_position(self) -> Optional[Position]:
        return None

    def __lt__(self, other: "Message"):
        pos = self.get_position()
        other_pos = other.get_position()
        if pos is None:
            return True
        elif other_pos is None:
            return False
        else:
            return pos < other_pos


class PositionMessage(Message):
    def __init__(
        self,
        level: Level,
        pos: Position,
        msg: str,
    ):
        super().__init__(level, msg)
        self.pos = pos

    def get_position(self) -> Optional[Position]:
        return self.pos
