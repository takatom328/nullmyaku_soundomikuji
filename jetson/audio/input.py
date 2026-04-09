from dataclasses import dataclass
import logging
import shutil
import struct
import subprocess
import time as time_module
from threading import Lock
from threading import Thread
from time import time

from ..utils.config import AudioConfig


@dataclass
class AudioFrame:
    timestamp: float
    samples: list


class AudioInput:
    """Captures the latest block from a live microphone when available."""

    def __init__(self, config: AudioConfig) -> None:
        self.config = config
        self._logger = logging.getLogger(__name__)
        self._lock = Lock()
        self._latest_timestamp = 0.0
        self._latest_samples = [0.0] * self.config.block_size
        self._stream = None
        self._arecord_process = None
        self._arecord_thread = None
        self._stop_requested = False
        self._started = False
        self._start_attempted = False
        self._active_backend = "silent"
        self._frames_received = 0
        self._fallback_warned = False

    def _normalize_samples(self, samples) -> list:
        normalized = [float(sample) for sample in samples[: self.config.block_size]]
        if len(normalized) < self.config.block_size:
            normalized.extend([0.0] * (self.config.block_size - len(normalized)))
        return normalized

    def _set_latest_samples(self, samples) -> None:
        with self._lock:
            self._latest_samples = self._normalize_samples(samples)
            self._latest_timestamp = time()
            self._frames_received += 1

    def _audio_callback(self, indata, frames, time_info, status) -> None:
        if status:
            self._logger.warning("Audio input status: %s", status)

        if self.config.channels == 1:
            channel_data = indata[:, 0]
        else:
            channel_data = indata.mean(axis=1)

        samples = self._normalize_samples(
            channel_data.tolist() if hasattr(channel_data, "tolist") else channel_data
        )
        self._set_latest_samples(samples)

    def _start_sounddevice(self) -> bool:
        try:
            import sounddevice as sd
        except ImportError:
            return False

        stream_kwargs = {
            "channels": self.config.channels,
            "samplerate": self.config.sample_rate_hz,
            "blocksize": self.config.block_size,
            "callback": self._audio_callback,
        }
        input_device = getattr(self.config, "input_device", "")
        if input_device:
            stream_kwargs["device"] = input_device

        self._stream = sd.InputStream(**stream_kwargs)
        self._stream.start()
        self._active_backend = "sounddevice"
        self._started = True
        return True

    def _pcm16le_to_mono(self, audio_bytes):
        if not audio_bytes:
            return []

        sample_count = len(audio_bytes) // 2
        if sample_count <= 0:
            return []

        unpacked = struct.unpack("<%dh" % sample_count, audio_bytes[: sample_count * 2])
        channels = max(self.config.channels, 1)

        if channels == 1:
            return [sample / 32768.0 for sample in unpacked]

        frame_count = len(unpacked) // channels
        mono = []
        for frame_index in range(frame_count):
            base = frame_index * channels
            frame = unpacked[base : base + channels]
            mono.append(sum(frame) / float(len(frame) * 32768.0))
        return mono

    def _arecord_reader_loop(self) -> None:
        bytes_per_frame = max(self.config.channels, 1) * 2
        bytes_per_block = self.config.block_size * bytes_per_frame

        while not self._stop_requested and self._arecord_process is not None:
            chunk = self._arecord_process.stdout.read(bytes_per_block)
            if not chunk:
                if self._arecord_process.poll() is not None:
                    break
                continue
            samples = self._pcm16le_to_mono(chunk)
            if samples:
                self._set_latest_samples(samples)

    def _start_arecord(self) -> bool:
        if shutil.which("arecord") is None:
            return False

        arecord_device = getattr(self.config, "arecord_device", "")
        device = arecord_device
        command = [
            "arecord",
            "-q",
            "-r",
            str(self.config.sample_rate_hz),
            "-f",
            "S16_LE",
            "-c",
            str(self.config.channels),
            "-t",
            "raw",
        ]
        if device:
            command.extend(["-D", device])

        self._arecord_process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )

        time_module.sleep(0.15)
        return_code = self._arecord_process.poll()
        if return_code is not None:
            error_text = ""
            if self._arecord_process.stderr is not None:
                try:
                    error_text = self._arecord_process.stderr.read().decode(
                        "utf-8", errors="ignore"
                    ).strip()
                except Exception:
                    error_text = ""
            self._arecord_process = None
            raise RuntimeError(
                "arecord exited immediately (code=%s). %s"
                % (return_code, error_text or "Check AUDIO_ARECORD_DEVICE and mic access.")
            )

        self._stop_requested = False
        self._arecord_thread = Thread(target=self._arecord_reader_loop, daemon=True)
        self._arecord_thread.start()
        self._active_backend = "arecord"
        self._started = True
        return True

    def start(self) -> None:
        if self._started or self._start_attempted:
            return
        self._start_attempted = True

        backend = (getattr(self.config, "backend", "auto") or "auto").lower()
        candidates = []
        if backend == "auto":
            candidates = ["arecord", "sounddevice"]
        elif backend in ("arecord", "sounddevice"):
            candidates = [backend]
        else:
            self._logger.warning(
                "Unknown AUDIO_BACKEND=%s. Falling back to silent audio.",
                getattr(self.config, "backend", ""),
            )
            candidates = []

        for candidate in candidates:
            try:
                if candidate == "arecord" and self._start_arecord():
                    break
                if candidate == "sounddevice" and self._start_sounddevice():
                    break
            except Exception as exc:
                self._logger.warning("Failed to start %s backend: %s", candidate, exc)

        if self._started:
            self._logger.info(
                "Audio input started with backend=%s at %s Hz, block size %s",
                self._active_backend,
                self.config.sample_rate_hz,
                self.config.block_size,
            )
            if self._active_backend == "arecord":
                self._logger.info(
                    "arecord device: %s",
                    getattr(self.config, "arecord_device", "") or "(default)",
                )
            return

        if not self._fallback_warned:
            self._logger.warning(
                "No audio backend could start. Falling back to silent audio frames."
            )
            self._fallback_warned = True

    def stop(self) -> None:
        self._stop_requested = True

        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None

        if self._arecord_process is not None:
            try:
                self._arecord_process.terminate()
                self._arecord_process.wait(timeout=1.0)
            except Exception:
                self._arecord_process.kill()
            finally:
                self._arecord_process = None

        if self._arecord_thread is not None:
            self._arecord_thread.join(timeout=1.0)
            self._arecord_thread = None

        self._started = False

    def get_frame(self) -> AudioFrame:
        if not self._started:
            self.start()

        with self._lock:
            timestamp = self._latest_timestamp or time()
            samples = list(self._latest_samples)

        return AudioFrame(timestamp=timestamp, samples=samples)

    def status(self):
        with self._lock:
            latest_timestamp = self._latest_timestamp
            frames_received = self._frames_received
        age_sec = None
        if latest_timestamp > 0:
            age_sec = round(max(0.0, time() - latest_timestamp), 3)
        return {
            "backend": self._active_backend,
            "started": self._started,
            "frames_received": frames_received,
            "latest_frame_age_sec": age_sec,
        }
