from dataclasses import dataclass
from collections import deque
import json
import logging
import socket
from threading import Lock
from threading import Thread
from time import time

from ..utils.config import IMUConfig


@dataclass
class IMUSample:
    timestamp: float
    ax: float
    ay: float
    az: float
    acc_norm: float
    event: str = None


class IMUReceiver:
    """Receives IMU samples from M5Stack and keeps a short recent window."""

    def __init__(self, config: IMUConfig) -> None:
        self.config = config
        self._logger = logging.getLogger(__name__)
        self._lock = Lock()
        self._samples = deque(maxlen=max(self.config.buffer_size, 32))
        self._socket = None
        self._thread = None
        self._started = False
        self._stop_requested = False
        self._frames_received = 0
        self._latest_timestamp = 0.0
        self._latest_event = None
        self._events = deque(maxlen=64)

    def _parse_payload(self, payload_text):
        now = time()
        try:
            payload = json.loads(payload_text)
        except Exception:
            return None

        if not isinstance(payload, dict):
            return None

        timestamp = payload.get("timestamp")
        try:
            timestamp = float(timestamp) if timestamp is not None else now
        except Exception:
            timestamp = now

        # M5Stack sender often uses millis()/1000.0 (relative time).
        # Convert relative/device-local timestamps to host receive time so
        # recent-window filtering and frame age stay meaningful.
        if timestamp < 1000000000.0:
            timestamp = now

        ax = float(payload.get("ax", 0.0))
        ay = float(payload.get("ay", 0.0))
        az = float(payload.get("az", 0.0))
        acc_norm = payload.get("acc_norm")
        if acc_norm is None:
            acc_norm = (ax * ax + ay * ay + az * az) ** 0.5
        else:
            acc_norm = float(acc_norm)
        event = payload.get("event")
        if event is not None:
            event = str(event)

        return IMUSample(
            timestamp=timestamp,
            ax=ax,
            ay=ay,
            az=az,
            acc_norm=acc_norm,
            event=event,
        )

    def _udp_reader_loop(self):
        while not self._stop_requested and self._socket is not None:
            try:
                packet, _addr = self._socket.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break

            try:
                text = packet.decode("utf-8", errors="ignore").strip()
                sample = self._parse_payload(text)
            except Exception:
                sample = None

            if sample is None:
                continue

            with self._lock:
                self._samples.append(sample)
                self._frames_received += 1
                self._latest_timestamp = sample.timestamp
                self._latest_event = sample.event
                if sample.event in ("start", "stop"):
                    self._events.append(
                        {
                            "event": sample.event,
                            "timestamp": sample.timestamp,
                        }
                    )

    def _start_udp(self):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((self.config.udp_host, self.config.udp_port))
        self._socket.settimeout(0.25)
        self._thread = Thread(target=self._udp_reader_loop, daemon=True)
        self._thread.start()
        self._logger.info(
            "IMU receiver listening on udp://%s:%s",
            self.config.udp_host,
            self.config.udp_port,
        )

    def start(self):
        if self._started:
            return

        transport = (self.config.transport or "udp").lower()
        self._stop_requested = False

        if transport == "udp":
            try:
                self._start_udp()
                self._started = True
            except Exception as exc:
                self._logger.warning(
                    "Failed to start UDP IMU receiver (%s:%s): %s",
                    self.config.udp_host,
                    self.config.udp_port,
                    exc,
                )
                self._started = False
            return

        self._logger.warning(
            "Unsupported IMU transport '%s'. Receiver stays idle.",
            self.config.transport,
        )
        self._started = False

    def stop(self):
        self._stop_requested = True

        if self._socket is not None:
            try:
                self._socket.close()
            finally:
                self._socket = None

        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

        self._started = False

    def get_recent_samples(self):
        now = time()
        cutoff = now - max(self.config.window_sec, 0.1)
        with self._lock:
            samples = [sample for sample in self._samples if sample.timestamp >= cutoff]
        return samples

    def status(self):
        with self._lock:
            frames_received = self._frames_received
            latest_timestamp = self._latest_timestamp
            latest_event = self._latest_event
            buffer_size = len(self._samples)
            pending_events = len(self._events)
        age_sec = None
        if latest_timestamp > 0:
            age_sec = round(max(0.0, time() - latest_timestamp), 3)
        return {
            "transport": self.config.transport,
            "started": self._started,
            "frames_received": frames_received,
            "latest_frame_age_sec": age_sec,
            "latest_event": latest_event,
            "buffer_size": buffer_size,
            "pending_events": pending_events,
        }

    def consume_events(self):
        with self._lock:
            events = list(self._events)
            self._events.clear()
        return events
