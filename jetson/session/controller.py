from collections import Counter
from time import time
from uuid import uuid4

from ..utils.config import SessionConfig


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _round_if_number(value):
    if _is_number(value):
        return round(float(value), 4)
    return value


def _aggregate_dicts(dicts):
    if not dicts:
        return {}

    keys = set()
    for item in dicts:
        keys.update(item.keys())

    aggregated = {}
    for key in keys:
        values = [item.get(key) for item in dicts if key in item]
        if not values:
            continue

        if all(_is_number(value) for value in values):
            aggregated[key] = _round_if_number(sum(values) / len(values))
            continue

        if all(isinstance(value, list) for value in values):
            lengths = [len(value) for value in values]
            if lengths and len(set(lengths)) == 1 and lengths[0] > 0:
                size = lengths[0]
                if all(all(_is_number(v) for v in value) for value in values):
                    averaged = []
                    for index in range(size):
                        averaged.append(sum(value[index] for value in values) / len(values))
                    aggregated[key] = [_round_if_number(value) for value in averaged]
                    continue

        aggregated[key] = values[-1]

    return aggregated


def _majority_label(dicts, label_key):
    labels = [item.get(label_key) for item in dicts if item.get(label_key)]
    if not labels:
        return None
    return Counter(labels).most_common(1)[0][0]


class SessionController:
    def __init__(self, config: SessionConfig) -> None:
        self.config = config
        self._active = False
        self._session_id = None
        self._started_at = None
        self._frames = []
        self._last_completed = None
        self._last_stop_reason = None
        self._cooldown_until = 0.0

    def _begin(self, now):
        self._active = True
        self._session_id = str(uuid4())
        self._started_at = now
        self._frames = []
        self._last_stop_reason = None

    def _end(self, now, stop_reason):
        if not self._active:
            return None

        started_at = self._started_at or now
        duration_sec = max(0.0, now - started_at)
        frame_count = len(self._frames)
        frames = self._frames
        session_id = self._session_id

        self._active = False
        self._session_id = None
        self._started_at = None
        self._frames = []
        self._last_stop_reason = stop_reason
        self._cooldown_until = now + max(0.0, self.config.cooldown_sec)

        if frame_count == 0:
            return None

        audio_dicts = [frame["audio_features"] for frame in frames]
        imu_dicts = [frame["imu_features"] for frame in frames]
        state_dicts = [frame["state"] for frame in frames]

        audio_features = _aggregate_dicts(audio_dicts)
        imu_features = _aggregate_dicts(imu_dicts)
        state = _aggregate_dicts(state_dicts)

        state_label = _majority_label(state_dicts, "state")
        if state_label:
            state["state"] = state_label
        state_source = _majority_label(state_dicts, "state_source")
        if state_source:
            state["state_source"] = state_source

        session_meta = {
            "session_id": session_id,
            "started_at": started_at,
            "ended_at": now,
            "duration_sec": round(duration_sec, 3),
            "stop_reason": stop_reason,
            "frame_count": frame_count,
        }
        result = {
            "meta": session_meta,
            "audio_features": audio_features,
            "imu_features": imu_features,
            "state": state,
        }
        self._last_completed = session_meta
        return result

    def process_frame(self, audio_features, imu_features, state, events):
        now = time()
        event_names = [str(event.get("event", "")).lower() for event in events]
        start_requested = "start" in event_names
        stop_requested = "stop" in event_names

        if not self.config.enabled:
            return None

        if not self._active:
            can_start = now >= self._cooldown_until
            if self.config.require_start_event:
                if start_requested and can_start:
                    self._begin(now)
            else:
                if can_start:
                    self._begin(now)

        if self._active:
            self._frames.append(
                {
                    "audio_features": dict(audio_features),
                    "imu_features": dict(imu_features),
                    "state": dict(state),
                    "timestamp": now,
                }
            )

            if len(self._frames) > max(self.config.max_frames, 32):
                self._frames = self._frames[-self.config.max_frames :]

            if stop_requested:
                duration = now - (self._started_at or now)
                if duration >= self.config.min_duration_sec:
                    return self._end(now, "stop_event")

            if self.config.auto_stop_sec > 0:
                duration = now - (self._started_at or now)
                if duration >= self.config.auto_stop_sec:
                    return self._end(now, "auto_timeout")

        return None

    def status(self):
        now = time()
        elapsed = 0.0
        if self._active and self._started_at is not None:
            elapsed = max(0.0, now - self._started_at)

        return {
            "enabled": self.config.enabled,
            "require_start_event": self.config.require_start_event,
            "active": self._active,
            "session_id": self._session_id,
            "elapsed_sec": round(elapsed, 3),
            "frame_count": len(self._frames),
            "last_completed": self._last_completed,
            "last_stop_reason": self._last_stop_reason,
        }
