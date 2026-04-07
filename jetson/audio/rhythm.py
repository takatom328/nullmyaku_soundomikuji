from __future__ import annotations


def estimate_onsets(samples: list[float], threshold: float = 0.1) -> int:
    if len(samples) < 2:
        return 0

    onsets = 0
    previous = abs(samples[0])
    for sample in samples[1:]:
        current = abs(sample)
        if current - previous > threshold:
            onsets += 1
        previous = current
    return onsets


def estimate_tempo_bpm(onset_count: int, window_seconds: float) -> float:
    if onset_count <= 1 or window_seconds <= 0:
        return 0.0
    return (onset_count / window_seconds) * 60.0
