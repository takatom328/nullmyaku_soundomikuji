from __future__ import annotations

from .ai.client import AIClient
from .audio.features import compute_audio_features
from .audio.input import AudioInput
from .fusion.state_estimator import estimate_state
from .imu.features import compute_imu_features
from .imu.receiver import IMUReceiver
from .printer.printer import Printer
from .utils.config import AppConfig
from .utils.logger import configure_logging


def run_once(config: AppConfig) -> None:
    logger = configure_logging()
    audio_input = AudioInput(config.audio)
    imu_receiver = IMUReceiver(config.imu)
    ai_client = AIClient(config.ai)
    printer = Printer(config.printer)

    audio_frame = audio_input.get_frame()
    imu_samples = imu_receiver.get_recent_samples()

    audio_features = compute_audio_features(audio_frame, config.audio.sample_rate_hz)
    imu_features = compute_imu_features(imu_samples)
    state = estimate_state(audio_features, imu_features)

    omikuji_text = ai_client.generate_omikuji(
        audio_features=audio_features,
        imu_features=imu_features,
        state=state,
        transcript=None,
    )

    logger.info("Estimated state: %s", state["state"])
    printer.print_omikuji(state["state"], omikuji_text)


def main() -> None:
    config = AppConfig.default()
    run_once(config)


if __name__ == "__main__":
    main()
