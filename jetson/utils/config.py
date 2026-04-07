from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AudioConfig:
    sample_rate_hz: int = 44100
    block_size: int = 1024
    channels: int = 1


@dataclass(frozen=True)
class IMUConfig:
    sample_rate_hz: int = 50
    transport: str = "mqtt"
    topic: str = "imu/data"


@dataclass(frozen=True)
class AIConfig:
    model: str = "set-model-here"
    endpoint: str = "responses"


@dataclass(frozen=True)
class PrinterConfig:
    transport: str = "stdout"


@dataclass(frozen=True)
class AppConfig:
    audio: AudioConfig
    imu: IMUConfig
    ai: AIConfig
    printer: PrinterConfig

    @classmethod
    def default(cls) -> "AppConfig":
        return cls(
            audio=AudioConfig(),
            imu=IMUConfig(),
            ai=AIConfig(),
            printer=PrinterConfig(),
        )
