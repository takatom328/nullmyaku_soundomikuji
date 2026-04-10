from time import sleep, time

from .ai.client import AIClient
from .audio.features import compute_audio_features
from .audio.input import AudioInput
from .fusion.model_runner import LocalModelRunner
from .fusion.state_estimator import estimate_state
from .imu.features import compute_imu_features
from .imu.receiver import IMUReceiver
from .printer.printer import Printer
from .session.archive import SessionArchive
from .session.controller import SessionController
from .utils.config import AppConfig
from .utils.logger import configure_logging
from .web.server import start_server_in_background
from .web.store import TelemetryStore


def collect_features(config: AppConfig, audio_input, imu_receiver, model_runner):
    audio_frame = audio_input.get_frame()
    imu_samples = imu_receiver.get_recent_samples()

    audio_features = compute_audio_features(audio_frame, config.audio.sample_rate_hz)
    imu_features = compute_imu_features(imu_samples)
    state = estimate_state(
        audio_features,
        imu_features,
        model_runner=model_runner,
        confidence_threshold=config.local_model.confidence_threshold,
    )
    return audio_features, imu_features, state


def build_snapshot(
    audio_input,
    imu_receiver,
    ai_client,
    audio_features,
    imu_features,
    state,
    session_controller,
    session_archive,
    model_runner,
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
        "session_archive": session_archive.status(),
        "local_model": model_runner.status(),
        "printer": printer_info,
    }


def main() -> None:
    config = AppConfig.default()
    logger = configure_logging()
    audio_input = AudioInput(config.audio)
    imu_receiver = IMUReceiver(config.imu)
    model_runner = LocalModelRunner(config.local_model, logger)
    ai_client = AIClient(config.ai)
    session_controller = SessionController(config.session)
    session_archive = SessionArchive(config.session, logger)
    printer = Printer(config.printer)
    telemetry_store = None
    printer_info = {}
    last_logged_state = None

    try:
        audio_input.start()
        imu_receiver.start()

        process_interval_sec = max(config.web.process_interval_sec, 0.03)
        telemetry_interval_sec = max(config.web.sample_interval_sec, 0.05)
        next_telemetry_at = 0.0
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
                model_runner=model_runner,
            )
            events = imu_receiver.consume_events()
            session_result = session_controller.process_frame(
                audio_features=audio_features,
                imu_features=imu_features,
                state=state,
                events=events,
            )

            if session_result is not None:
                expo_recommendation = printer.create_expo_recommendation()
                omikuji_text = ai_client.generate_omikuji(
                    audio_features=session_result["audio_features"],
                    imu_features=session_result["imu_features"],
                    state=session_result["state"],
                    transcript=None,
                    expo_recommendation=expo_recommendation,
                )
                print_job = printer.build_print_job(
                    session_result["state"]["state"],
                    omikuji_text,
                    audio_features=session_result["audio_features"],
                    imu_features=session_result["imu_features"],
                    state_features=session_result["state"],
                    expo_recommendation=expo_recommendation,
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
                archived = session_archive.save(
                    {
                        "meta": session_result["meta"],
                        "audio_features": session_result["audio_features"],
                        "imu_features": session_result["imu_features"],
                        "state": session_result["state"],
                        "generated": {
                            "omikuji_text": omikuji_text,
                            "expo_recommendation": expo_recommendation,
                            "ai": ai_client.status(),
                            "printer": {
                                "job_id": print_job["job_id"],
                                "transport": config.printer.transport,
                            },
                        },
                    }
                )
                if archived is not None:
                    session_result["archive"] = archived
                    logger.info("Session archived: %s", archived["filename"])
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
                session_archive=session_archive,
                model_runner=model_runner,
                printer_info=printer_info,
            )
            if session_result is not None:
                snapshot["session_completed"] = session_result

            now = time()
            if telemetry_store is not None and now >= next_telemetry_at:
                telemetry_store.update(snapshot)
                next_telemetry_at = now + telemetry_interval_sec

            sleep(process_interval_sec)
    except KeyboardInterrupt:
        logger.info("Stopping main loop")
    finally:
        audio_input.stop()
        imu_receiver.stop()


if __name__ == "__main__":
    main()
