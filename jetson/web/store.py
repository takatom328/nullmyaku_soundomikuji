from collections import deque
from copy import deepcopy
from dataclasses import dataclass, field
from threading import Lock
from time import time


@dataclass
class TelemetryStore:
    history_size: int = 120
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)
    _latest: dict = field(default_factory=dict, init=False, repr=False)
    _history: deque = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._history = deque(maxlen=self.history_size)

    def update(self, snapshot) -> None:
        with self._lock:
            payload = deepcopy(snapshot)
            payload.setdefault("updated_at", time())
            self._latest = payload
            self._history.append(payload)

    def latest(self):
        with self._lock:
            return deepcopy(self._latest)

    def history(self):
        with self._lock:
            return deepcopy(list(self._history))
