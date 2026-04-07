from __future__ import annotations


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def estimate_state(
    audio_features: dict[str, float | list[float]],
    imu_features: dict[str, float],
) -> dict[str, float | str]:
    rms = float(audio_features.get("rms", 0.0))
    centroid = float(audio_features.get("spectral_centroid", 0.0))
    tempo = float(audio_features.get("tempo_bpm", 0.0))
    movement = float(imu_features.get("movement_intensity", 0.0))

    energy = _clamp((rms * 1.8) + (movement * 0.7))
    brightness = _clamp(centroid / 4000.0)
    rhythm_stability = _clamp(1.0 - abs(tempo - 96.0) / 96.0)
    movement_intensity = _clamp(movement)

    if energy > 0.7 and movement_intensity > 0.5:
        state = "energetic"
    elif brightness > 0.6 and energy < 0.4:
        state = "delicate"
    elif rhythm_stability > 0.7:
        state = "focused"
    elif movement_intensity > 0.4:
        state = "open"
    else:
        state = "unstable"

    return {
        "energy": round(energy, 4),
        "brightness": round(brightness, 4),
        "rhythm_stability": round(rhythm_stability, 4),
        "movement_intensity": round(movement_intensity, 4),
        "state": state,
    }
