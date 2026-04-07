from __future__ import annotations

from .receiver import IMUSample


def compute_imu_features(samples: list[IMUSample]) -> dict[str, float]:
    if not samples:
        return {
            "mean_acc_norm": 0.0,
            "peak_acc_norm": 0.0,
            "movement_frequency_hz": 0.0,
            "movement_intensity": 0.0,
        }

    norms = [sample.acc_norm for sample in samples]
    mean_acc = sum(norms) / len(norms)
    peak_acc = max(norms)
    moving = sum(1 for value in norms if value > 1.1)
    movement_frequency = moving / max(len(samples), 1)
    movement_intensity = max(0.0, peak_acc - 1.0)

    return {
        "mean_acc_norm": round(mean_acc, 4),
        "peak_acc_norm": round(peak_acc, 4),
        "movement_frequency_hz": round(movement_frequency, 4),
        "movement_intensity": round(movement_intensity, 4),
    }
