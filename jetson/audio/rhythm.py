import math


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
