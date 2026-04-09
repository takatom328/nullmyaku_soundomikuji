from dataclasses import dataclass
import os
from pathlib import Path


_DOTENV_LOADED = False


def _strip_inline_comment(raw_value: str) -> str:
    value = raw_value.strip()
    if not value:
        return value
    if (value[0] == value[-1]) and value[0] in ("'", '"'):
        return value[1:-1]
    if " #" in value:
        return value.split(" #", 1)[0].rstrip()
    return value


def _load_dotenv_file(dotenv_path: Path) -> None:
    try:
        lines = dotenv_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue

        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = _strip_inline_comment(raw_value)
        os.environ.setdefault(key, value)


def _auto_load_dotenv() -> None:
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    _DOTENV_LOADED = True

    project_root = Path(__file__).resolve().parents[2]
    candidate_paths = []

    custom_path = os.getenv("APP_DOTENV_PATH", "").strip()
    if custom_path:
        candidate_paths.append(Path(custom_path).expanduser())
    candidate_paths.append(Path.cwd() / ".env")
    candidate_paths.append(project_root / ".env")

    visited = set()
    for path in candidate_paths:
        try:
            normalized = path.resolve()
        except OSError:
            normalized = path
        marker = str(normalized)
        if marker in visited:
            continue
        visited.add(marker)
        if normalized.is_file():
            _load_dotenv_file(normalized)


@dataclass(frozen=True)
class AudioConfig:
    sample_rate_hz: int = 44100
    block_size: int = 1024
    channels: int = 1
    backend: str = "auto"
    input_device: str = ""
    arecord_device: str = ""


@dataclass(frozen=True)
class IMUConfig:
    sample_rate_hz: int = 50
    transport: str = "udp"
    topic: str = "imu/data"
    udp_host: str = "0.0.0.0"
    udp_port: int = 9001
    buffer_size: int = 512
    window_sec: float = 3.0


@dataclass(frozen=True)
class AIConfig:
    mode: str = "local"
    model: str = "gpt-4.1-mini"
    endpoint: str = "responses"
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    timeout_sec: float = 12.0
    fallback_enabled: bool = True


@dataclass(frozen=True)
class PrinterConfig:
    transport: str = "stdout"
    endpoint_url: str = "http://raspberrypi.local:8000/print-jobs"
    timeout_sec: float = 5.0
    auth_token: str = ""
    source_device: str = "jetson-nano"


@dataclass(frozen=True)
class SessionConfig:
    enabled: bool = True
    require_start_event: bool = True
    auto_stop_sec: float = 10.0
    min_duration_sec: float = 1.0
    cooldown_sec: float = 0.8
    max_frames: int = 1200


@dataclass(frozen=True)
class AppConfig:
    audio: AudioConfig
    imu: IMUConfig
    ai: AIConfig
    session: SessionConfig
    printer: PrinterConfig
    web: "WebConfig"

    @classmethod
    def default(cls) -> "AppConfig":
        _auto_load_dotenv()
        return cls(
            audio=AudioConfig(
                sample_rate_hz=int(os.getenv("AUDIO_SAMPLE_RATE_HZ", "44100")),
                block_size=int(os.getenv("AUDIO_BLOCK_SIZE", "1024")),
                channels=int(os.getenv("AUDIO_CHANNELS", "1")),
                backend=os.getenv("AUDIO_BACKEND", "auto"),
                input_device=os.getenv("AUDIO_INPUT_DEVICE", ""),
                arecord_device=os.getenv("AUDIO_ARECORD_DEVICE", ""),
            ),
            imu=IMUConfig(
                sample_rate_hz=int(os.getenv("IMU_SAMPLE_RATE_HZ", "50")),
                transport=os.getenv("IMU_TRANSPORT", "udp"),
                topic=os.getenv("IMU_TOPIC", "imu/data"),
                udp_host=os.getenv("IMU_UDP_HOST", "0.0.0.0"),
                udp_port=int(os.getenv("IMU_UDP_PORT", "9001")),
                buffer_size=int(os.getenv("IMU_BUFFER_SIZE", "512")),
                window_sec=float(os.getenv("IMU_WINDOW_SEC", "3.0")),
            ),
            ai=AIConfig(
                mode=os.getenv("AI_MODE", "local"),
                model=os.getenv("AI_MODEL", "gpt-4.1-mini"),
                endpoint=os.getenv("AI_ENDPOINT", "responses"),
                api_key=os.getenv("OPENAI_API_KEY", ""),
                base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
                timeout_sec=float(os.getenv("AI_TIMEOUT_SEC", "12.0")),
                fallback_enabled=os.getenv("AI_FALLBACK_ENABLED", "1") != "0",
            ),
            session=SessionConfig(
                enabled=os.getenv("SESSION_ENABLED", "1") != "0",
                require_start_event=os.getenv("SESSION_REQUIRE_START_EVENT", "1")
                != "0",
                auto_stop_sec=float(os.getenv("SESSION_AUTO_STOP_SEC", "10.0")),
                min_duration_sec=float(os.getenv("SESSION_MIN_DURATION_SEC", "1.0")),
                cooldown_sec=float(os.getenv("SESSION_COOLDOWN_SEC", "0.8")),
                max_frames=int(os.getenv("SESSION_MAX_FRAMES", "1200")),
            ),
            printer=PrinterConfig(
                transport=os.getenv("PRINTER_TRANSPORT", "stdout"),
                endpoint_url=os.getenv(
                    "PRINTER_ENDPOINT_URL",
                    "http://raspberrypi.local:8000/print-jobs",
                ),
                timeout_sec=float(os.getenv("PRINTER_TIMEOUT_SEC", "5.0")),
                auth_token=os.getenv("PRINTER_AUTH_TOKEN", ""),
                source_device=os.getenv("PRINTER_SOURCE_DEVICE", "jetson-nano"),
            ),
            web=WebConfig(
                enabled=os.getenv("WEB_DASHBOARD_ENABLED", "0") == "1",
                host=os.getenv("WEB_DASHBOARD_HOST", "0.0.0.0"),
                port=int(os.getenv("WEB_DASHBOARD_PORT", "5000")),
                sample_interval_sec=float(os.getenv("WEB_SAMPLE_INTERVAL_SEC", "0.5")),
                history_size=int(os.getenv("WEB_HISTORY_SIZE", "120")),
            ),
        )


@dataclass(frozen=True)
class WebConfig:
    enabled: bool = False
    host: str = "0.0.0.0"
    port: int = 5000
    sample_interval_sec: float = 0.5
    history_size: int = 120
