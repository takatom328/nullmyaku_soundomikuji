from __future__ import annotations

from ..utils.config import AIConfig


class AIClient:
    """Local placeholder for the future Responses API integration."""

    def __init__(self, config: AIConfig) -> None:
        self.config = config

    def build_payload(
        self,
        audio_features: dict[str, float | list[float]],
        imu_features: dict[str, float],
        state: dict[str, float | str],
        transcript: str | None,
    ) -> dict[str, object]:
        return {
            "model": self.config.model,
            "audio_features": audio_features,
            "imu_features": imu_features,
            "derived_state": state,
            "transcript": transcript,
        }

    def generate_omikuji(
        self,
        audio_features: dict[str, float | list[float]],
        imu_features: dict[str, float],
        state: dict[str, float | str],
        transcript: str | None,
    ) -> str:
        _payload = self.build_payload(audio_features, imu_features, state, transcript)
        current_state = state["state"]
        return (
            f"あなたの今の状態は {current_state} です。\n"
            "身体が先に動く日です。迷いよりも、最初の一歩を信じてください。"
        )
