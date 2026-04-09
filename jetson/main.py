from time import sleep

from .ai.client import AIClient
from .audio.features import compute_audio_features
from .audio.input import AudioInput
from .fusion.state_estimator import estimate_state
from .imu.features import compute_imu_features
from .imu.receiver import IMUReceiver
from .printer.printer import Printer
from .session.controller import SessionController
from .utils.config import AppConfig
from .utils.logger import configure_logging
from .web.server import start_server_in_background
from .web.store import TelemetryStore


def collect_features(config: AppConfig, audio_input, imu_receiver):
    audio_frame = audio_input.get_frame()
    imu_samples = imu_receiver.get_recent_samples()

    audio_features = compute_audio_features(audio_frame, config.audio.sample_rate_hz)
    imu_features = compute_imu_features(imu_samples)
    state = estimate_state(audio_features, imu_features)
    return audio_features, imu_features, state


def build_snapshot(
    audio_input,
    imu_receiver,
    ai_client,
    audio_features,
    imu_features,
    state,
    session_controller,
    printer_info,
):
    return {
        "audio_input": audio_input.status(),
        "imu_input": imu_receiver.status(),
        "audio_features": audio_features,
        "imu_features": imu_features,
        "state": state,
        "ai": ai_client.status(),
        "session": session_controller.status(),
        "printer": printer_info,
    }


def main() -> None:
    config = AppConfig.default()
    logger = configure_logging()
    audio_input = AudioInput(config.audio)
    imu_receiver = IMUReceiver(config.imu)
    ai_client = AIClient(config.ai)
    session_controller = SessionController(config.session)
    printer = Printer(config.printer)
    telemetry_store = None
    printer_info = {}
    last_logged_state = None

    try:
        audio_input.start()
        imu_receiver.start()

        loop_interval_sec = max(config.web.sample_interval_sec, 0.1)
        if config.web.enabled:
            telemetry_store = TelemetryStore(history_size=config.web.history_size)
            start_server_in_background(telemetry_store, config.web)
            logger.info(
                "Dashboard available at http://%s:%s",
                config.web.host,
                config.web.port,
            )

        while True:
            audio_features, imu_features, state = collect_features(
                config,
                audio_input=audio_input,
                imu_receiver=imu_receiver,
            )
            events = imu_receiver.consume_events()
            session_result = session_controller.process_frame(
                audio_features=audio_features,
                imu_features=imu_features,
                state=state,
                events=events,
            )

            if session_result is not None:
                omikuji_text = ai_client.generate_omikuji(
                    audio_features=session_result["audio_features"],
                    imu_features=session_result["imu_features"],
                    state=session_result["state"],
                    transcript=None,
                )
                print_job = printer.build_print_job(
                    session_result["state"]["state"], omikuji_text
                )
                printer.dispatch_print_job(print_job)
                printer_info = {
                    "job_id": print_job["job_id"],
                    "transport": config.printer.transport,
                    "ticket_text": print_job["ticket_text"],
                }
                logger.info(
                    "Session completed: id=%s state=%s reason=%s",
                    session_result["meta"]["session_id"],
                    session_result["state"]["state"],
                    session_result["meta"]["stop_reason"],
                )
            else:
                if state["state"] != last_logged_state:
                    logger.info("Estimated state: %s", state["state"])
                    last_logged_state = state["state"]

            snapshot = build_snapshot(
                audio_input=audio_input,
                imu_receiver=imu_receiver,
                ai_client=ai_client,
                audio_features=audio_features,
                imu_features=imu_features,
                state=state,
                session_controller=session_controller,
                printer_info=printer_info,
            )
            if session_result is not None:
                snapshot["session_completed"] = session_result

            if telemetry_store is not None:
                telemetry_store.update(snapshot)

            sleep(loop_interval_sec)
    except KeyboardInterrupt:
        logger.info("Stopping main loop")
    finally:
        audio_input.stop()
        imu_receiver.stop()


if __name__ == "__main__":
    main()
