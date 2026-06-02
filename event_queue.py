import queue
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventType(Enum):
    STEAM_STATUS_CHANGED = "steam_status_changed"
    SIGN_UPDATED = "sign_updated"
    COOKIE_EXPIRED = "cookie_expired"
    GAME_NAME_RESOLVED = "game_name_resolved"
    ERROR = "error"
    LOGIN_SUCCESS = "login_success"


@dataclass
class Event:
    type: EventType
    data: Any = None


class EventQueue:
    def __init__(self):
        self._queue: queue.Queue = queue.Queue()

    def put(self, event: Event):
        self._queue.put(event)

    def get_all(self) -> list[Event]:
        events = []
        while True:
            try:
                events.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return events

    def start_polling(self, root, callback, interval: int = 200):
        def _poll():
            events = self.get_all()
            if events:
                callback(events)
            root.after(interval, _poll)
        _poll()
