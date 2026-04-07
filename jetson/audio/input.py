from __future__ import annotations

from dataclasses import dataclass
from time import time

from ..utils.config import AudioConfig


@dataclass
class AudioFrame:
    timestamp: float
    samples: list[float]


class AudioInput:
    """Placeholder audio input for the first scaffold."""

    def __init__(self, config: AudioConfig) -> None:
        self.config = config

    def start(self) -> None:
        """Reserved for stream initialization."""

    def get_frame(self) -> AudioFrame:
        sample_count = self.config.block_size
        return AudioFrame(timestamp=time(), samples=[0.0] * sample_count)
