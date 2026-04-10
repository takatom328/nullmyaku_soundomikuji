import math
from collections import deque


def _clamp01(value):
    return max(0.0, min(1.0, value))


def _chunk_rms(samples):
    if not samples:
        return 0.0
    return math.sqrt(sum(sample * sample for sample in samples) / len(samples))


def compute_energy_envelope(samples, frame_size: int = 128):
    if not samples or frame_size <= 0:
        return []

    envelope = []
    for start in range(0, len(samples), frame_size):
        chunk = samples[start : start + frame_size]
        if chunk:
            envelope.append(_chunk_rms(chunk))
    return envelope


class TempoTracker:
    """Tracks onsets across multiple audio frames for stable tempo estimation."""

    def __init__(
        self,
        sample_rate_hz,
        envelope_frame_size=256,
        history_seconds=12.0,
        rise_threshold=1.18,
        min_gap_seconds=0.16,
    ):
        self.sample_rate_hz = max(int(sample_rate_hz), 1)
        self.envelope_frame_size = max(int(envelope_frame_size), 64)
        self.history_seconds = max(float(history_seconds), 3.0)
        self.rise_threshold = max(float(rise_threshold), 1.1)
        self.min_gap_seconds = max(float(min_gap_seconds), 0.08)
        self._history = deque()
        self._novelty_history = deque()
        self._hint_history = deque()
        self._onset_times = deque()
        self._onset_strengths = deque()
        self._last_envelope = 0.0
        self._last_onset_time = -9999.0
        self._last_update_ts = None

    def _prune(self, now_ts):
        threshold = now_ts - self.history_seconds
        while self._history and self._history[0][0] < threshold:
            self._history.popleft()
        while self._novelty_history and self._novelty_history[0][0] < threshold:
            self._novelty_history.popleft()
        while self._hint_history and self._hint_history[0][0] < threshold:
            self._hint_history.popleft()
        while self._onset_times and self._onset_times[0] < threshold:
            self._onset_times.popleft()
        while len(self._onset_strengths) > len(self._onset_times):
            self._onset_strengths.popleft()

    def _fold_bpm(self, bpm):
        if bpm <= 0.0:
            return 0.0
        while bpm < 70.0:
            bpm *= 2.0
        while bpm > 170.0:
            bpm /= 2.0
        return bpm

    def _estimate_from_autocorr(self):
        source = self._novelty_history if len(self._novelty_history) >= 80 else self._history
        if len(source) < 80:
            return None

        values = [value for _, value in source]
        if len(self._hint_history) == len(source):
            hint_values = [value for _, value in self._hint_history]
            values = [(value * 0.72) + (hint * 0.28) for value, hint in zip(values, hint_values)]
        mean_value = sum(values) / float(len(values))
        centered = [value - mean_value for value in values]

        energy = sum(value * value for value in centered)
        if energy <= 1e-9:
            return None

        if len(source) >= 2:
            total_dt = source[-1][0] - source[0][0]
            step_sec = total_dt / float(max(len(source) - 1, 1))
        else:
            step_sec = self.envelope_frame_size / float(self.sample_rate_hz)

        if step_sec <= 0:
            return None

        lag_min = int(0.28 / step_sec)
        lag_max = int(1.20 / step_sec)
        lag_min = max(2, lag_min)
        lag_max = min(len(centered) - 2, lag_max)
        if lag_max <= lag_min:
            return None

        best_lag = 0
        best_corr = -1e18
        for lag in range(lag_min, lag_max + 1):
            corr = 0.0
            for idx in range(lag, len(centered)):
                corr += centered[idx] * centered[idx - lag]
            if corr > best_corr:
                best_corr = corr
                best_lag = lag

        if best_lag <= 0 or best_corr <= 0:
            return None

        period_sec = best_lag * step_sec
        bpm = self._fold_bpm(60.0 / max(period_sec, 1e-9))
        confidence = _clamp01(best_corr / max(energy, 1e-9))
        if bpm < 45.0 or bpm > 220.0 or confidence < 0.08:
            return None
        return {
            "tempo_bpm": bpm,
            "tempo_confidence": confidence,
            "beat_period_sec": period_sec,
        }

    def _estimate_from_window(self):
        onset_rate_hz = len(self._onset_times) / self.history_seconds
        auto = self._estimate_from_autocorr()

        if len(self._onset_times) < 3:
            if auto is None:
                return {
                    "tempo_bpm": 0.0,
                    "tempo_confidence": 0.0,
                    "onset_rate_hz": onset_rate_hz,
                    "beat_strength": 0.0,
                    "beat_period_sec": 0.0,
                }
            return {
                "tempo_bpm": auto["tempo_bpm"],
                "tempo_confidence": auto["tempo_confidence"] * 0.75,
                "onset_rate_hz": onset_rate_hz,
                "beat_strength": auto["tempo_confidence"] * 0.55,
                "beat_period_sec": auto["beat_period_sec"],
            }

        intervals = []
        for prev, curr in zip(self._onset_times, list(self._onset_times)[1:]):
            dt = curr - prev
            if 0.18 <= dt <= 1.4:
                intervals.append(dt)

        if len(intervals) < 2:
            if auto is None:
                return {
                    "tempo_bpm": 0.0,
                    "tempo_confidence": 0.0,
                    "onset_rate_hz": onset_rate_hz,
                    "beat_strength": 0.0,
                    "beat_period_sec": 0.0,
                }
            return {
                "tempo_bpm": auto["tempo_bpm"],
                "tempo_confidence": auto["tempo_confidence"] * 0.8,
                "onset_rate_hz": onset_rate_hz,
                "beat_strength": auto["tempo_confidence"] * 0.6,
                "beat_period_sec": auto["beat_period_sec"],
            }

        intervals.sort()
        median_interval = intervals[len(intervals) // 2]
        mean_interval = sum(intervals) / len(intervals)
        variance = sum((value - mean_interval) ** 2 for value in intervals) / len(intervals)
        std_interval = variance ** 0.5
        cv = std_interval / max(mean_interval, 1e-9)

        raw_bpm = 60.0 / max(median_interval, 1e-9)
        tempo_bpm = self._fold_bpm(raw_bpm)

        rhythm_consistency = _clamp01(1.0 - cv * 1.9)
        density_score = _clamp01(onset_rate_hz / 3.0)
        confidence = _clamp01((rhythm_consistency * 0.7) + (density_score * 0.3))

        if self._onset_strengths:
            beat_strength = sum(self._onset_strengths) / len(self._onset_strengths)
        else:
            beat_strength = 0.0
        beat_strength = _clamp01(beat_strength)

        if auto is not None and auto["tempo_confidence"] > confidence + 0.08:
            tempo_bpm = auto["tempo_bpm"]
            median_interval = auto["beat_period_sec"]
            confidence = (confidence * 0.45) + (auto["tempo_confidence"] * 0.55)
            if beat_strength <= 0.02:
                beat_strength = auto["tempo_confidence"] * 0.6

        return {
            "tempo_bpm": tempo_bpm if 45.0 <= tempo_bpm <= 220.0 else 0.0,
            "tempo_confidence": confidence,
            "onset_rate_hz": onset_rate_hz,
            "beat_strength": beat_strength,
            "beat_period_sec": median_interval,
        }

    def update(self, frame_timestamp, samples, beat_signal_hint=0.0):
        if not samples:
            return {
                "tempo_bpm": 0.0,
                "tempo_confidence": 0.0,
                "onset_rate_hz": 0.0,
                "beat_strength": 0.0,
                "beat_period_sec": 0.0,
                "beat_detected": 0.0,
            }

        now_ts = float(frame_timestamp)
        block_duration = len(samples) / float(self.sample_rate_hz)
        start_ts = now_ts - block_duration

        envelope = compute_energy_envelope(samples, frame_size=self.envelope_frame_size)
        beat_detected = 0.0
        hint_value = max(0.0, float(beat_signal_hint or 0.0))
        hint_step = hint_value / float(max(len(envelope), 1))
        for index, energy in enumerate(envelope):
            if self._last_update_ts is not None:
                step = self.envelope_frame_size / float(self.sample_rate_hz)
                sample_ts = start_ts + ((index + 1) * step)
            else:
                sample_ts = now_ts

            self._history.append((sample_ts, energy))
            history_values = [value for _, value in self._history]
            baseline_window = history_values[-96:] if len(history_values) >= 8 else history_values
            baseline = sum(baseline_window) / max(len(baseline_window), 1)
            prev = max(self._last_envelope, 1e-9)
            dynamic_threshold = max(baseline * self.rise_threshold, baseline + 0.0009)
            rise = max(0.0, energy - prev)
            novelty = (rise * 0.85) + (max(0.0, energy - baseline) * 0.9)
            novelty += hint_step * 1.1
            self._novelty_history.append((sample_ts, novelty))
            self._hint_history.append((sample_ts, hint_step))
            novelty_values = [value for _, value in self._novelty_history]
            novelty_window = novelty_values[-96:] if len(novelty_values) >= 8 else novelty_values
            novelty_mean = sum(novelty_window) / max(len(novelty_window), 1)
            novelty_threshold = max(novelty_mean * 2.15, 0.00025)

            is_onset = (
                (energy > dynamic_threshold or novelty > novelty_threshold)
                and energy > prev * 1.02
                and (sample_ts - self._last_onset_time) >= self.min_gap_seconds
            )
            if is_onset:
                strength = _clamp01(
                    (novelty * 1.8 + (energy - baseline))
                    / max(baseline + 1e-6, 0.02)
                )
                self._onset_times.append(sample_ts)
                self._onset_strengths.append(strength)
                self._last_onset_time = sample_ts
                beat_detected = 1.0

            self._last_envelope = energy

        self._last_update_ts = now_ts
        self._prune(now_ts)
        summary = self._estimate_from_window()
        beat_recent = 1.0 if (now_ts - self._last_onset_time) <= 0.8 else 0.0
        summary["beat_detected"] = max(beat_detected, beat_recent)
        return summary


def detect_onset_times(
    samples,
    sample_rate_hz: int,
    frame_size: int = 128,
    rise_threshold: float = 1.5,
    min_gap_seconds: float = 0.12,
):
    if len(samples) < frame_size or sample_rate_hz <= 0:
        return []

    envelope = compute_energy_envelope(samples, frame_size=frame_size)
    if len(envelope) < 2:
        return []

    min_gap_frames = max(int((min_gap_seconds * sample_rate_hz) / frame_size), 1)
    onset_times = []
    last_onset_frame = -min_gap_frames

    for frame_index in range(1, len(envelope)):
        current = envelope[frame_index]
        previous = max(envelope[frame_index - 1], 1e-9)
        recent_window = envelope[max(0, frame_index - 4) : frame_index]
        baseline = sum(recent_window) / len(recent_window) if recent_window else previous

        if current <= 1e-6:
            continue

        if current > baseline * rise_threshold and current > previous * 1.1:
            if frame_index - last_onset_frame >= min_gap_frames:
                onset_times.append((frame_index * frame_size) / sample_rate_hz)
                last_onset_frame = frame_index

    return onset_times


def estimate_onsets(samples, sample_rate_hz: int) -> int:
    return len(detect_onset_times(samples, sample_rate_hz))


def estimate_tempo_bpm(onset_count: int, window_seconds: float) -> float:
    if onset_count <= 1 or window_seconds <= 0:
        return 0.0
    return (onset_count / window_seconds) * 60.0


def estimate_tempo_bpm_from_onsets(onset_times) -> float:
    if len(onset_times) < 2:
        return 0.0

    intervals = [
        current - previous
        for previous, current in zip(onset_times, onset_times[1:])
        if current > previous
    ]
    if not intervals:
        return 0.0

    intervals.sort()
    median_interval = intervals[len(intervals) // 2]
    if median_interval <= 0:
        return 0.0

    bpm = 60.0 / median_interval
    return bpm if 20.0 <= bpm <= 300.0 else 0.0
