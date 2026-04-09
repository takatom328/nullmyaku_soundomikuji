from .receiver import IMUSample


def _clamp01(value):
    return max(0.0, min(1.0, value))


def _estimate_imu_rhythm(norms, sample_rate_hz):
    if len(norms) < 6 or sample_rate_hz <= 0:
        return 0.0, 0.0, 0

    mean_norm = sum(norms) / len(norms)
    threshold = max(mean_norm + 0.06, 1.06)

    min_gap_samples = max(int(sample_rate_hz * 0.18), 1)
    peak_indices = []
    last_peak_index = -min_gap_samples

    for index in range(1, len(norms) - 1):
        current = norms[index]
        if (
            current > threshold
            and current >= norms[index - 1]
            and current >= norms[index + 1]
            and index - last_peak_index >= min_gap_samples
        ):
            peak_indices.append(index)
            last_peak_index = index

    if len(peak_indices) < 2:
        return 0.0, 0.0, len(peak_indices)

    intervals_sec = []
    for prev, curr in zip(peak_indices, peak_indices[1:]):
        intervals_sec.append((curr - prev) / sample_rate_hz)

    if not intervals_sec:
        return 0.0, 0.0, len(peak_indices)

    mean_interval = sum(intervals_sec) / len(intervals_sec)
    if mean_interval <= 0:
        return 0.0, 0.0, len(peak_indices)

    rhythm_hz = 1.0 / mean_interval
    variance = sum((value - mean_interval) ** 2 for value in intervals_sec) / len(intervals_sec)
    std = variance ** 0.5
    cv = std / mean_interval if mean_interval > 0 else 1.0
    rhythm_stability = _clamp01(1.0 - cv * 2.2)

    return rhythm_hz, rhythm_stability, len(peak_indices)


def compute_imu_features(samples):
    if not samples:
        return {
            "sample_count": 0,
            "mean_acc_norm": 0.0,
            "peak_acc_norm": 0.0,
            "movement_frequency_hz": 0.0,
            "movement_intensity": 0.0,
            "sample_rate_hz": 0.0,
            "rhythm_hz": 0.0,
            "rhythm_stability": 0.0,
            "peak_count": 0,
        }

    norms = [sample.acc_norm for sample in samples]
    mean_acc = sum(norms) / len(norms)
    peak_acc = max(norms)
    moving = sum(1 for value in norms if value > 1.08)

    timestamps = [sample.timestamp for sample in samples if sample.timestamp is not None]
    duration_sec = 0.0
    if len(timestamps) >= 2:
        duration_sec = max(timestamps) - min(timestamps)

    if duration_sec > 0:
        movement_frequency = moving / duration_sec
        sample_rate_hz = len(samples) / duration_sec
    else:
        movement_frequency = 0.0
        sample_rate_hz = 0.0

    movement_intensity = max(0.0, peak_acc - 1.0)
    rhythm_hz, rhythm_stability, peak_count = _estimate_imu_rhythm(norms, sample_rate_hz)

    return {
        "sample_count": len(samples),
        "mean_acc_norm": round(mean_acc, 4),
        "peak_acc_norm": round(peak_acc, 4),
        "movement_frequency_hz": round(movement_frequency, 4),
        "movement_intensity": round(movement_intensity, 4),
        "sample_rate_hz": round(sample_rate_hz, 4),
        "rhythm_hz": round(rhythm_hz, 4),
        "rhythm_stability": round(rhythm_stability, 4),
        "peak_count": peak_count,
    }
