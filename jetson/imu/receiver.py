from __future__ import annotations

from dataclasses import dataclass
from time import time

from ..utils.config import IMUConfig


@dataclass
class IMUSample:
    timestamp: float
    ax: float
    ay: float
    az: float
    acc_norm: float
    event: str | None = None


class IMUReceiver:
    """Placeholder receiver until MQTT or UDP is connected."""

    def __init__(self, config: IMUConfig) -> None:
        self.config = config

    def get_recent_samples(self) -> list[IMUSample]:
        return [
            IMUSample(timestamp=time(), ax=0.0, ay=0.0, az=1.0, acc_norm=1.0),
        ]
