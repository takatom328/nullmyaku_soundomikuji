from __future__ import annotations

import math

from .fft import compute_band_energies
from .input import AudioFrame
from .rhythm import estimate_onsets, estimate_tempo_bpm


def compute_audio_features(frame: AudioFrame, sample_rate_hz: int) -> dict[str, float | list[float]]:
    samples = frame.samples
    if not samples:
        return {
            "rms": 0.0,
            "spectral_centroid": 0.0,
            "band_energies": [0.0] * 16,
            "low_mid_high_ratio": [0.0, 0.0, 0.0],
            "onset_count": 0,
            "tempo_bpm": 0.0,
        }

    rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
    band_energies = compute_band_energies(samples, band_count=16)
    total_energy = sum(band_energies) or 1.0
    weighted_sum = sum(index * energy for index, energy in enumerate(band_energies))
    centroid = (weighted_sum / total_energy) * (sample_rate_hz / 2) / len(band_energies)

    low = sum(band_energies[:5]) / total_energy
    mid = sum(band_energies[5:11]) / total_energy
    high = sum(band_energies[11:]) / total_energy

    duration_sec = len(samples) / sample_rate_hz if sample_rate_hz > 0 else 0.0
    onset_count = estimate_onsets(samples)
    tempo_bpm = estimate_tempo_bpm(onset_count, duration_sec)

    return {
        "rms": round(rms, 4),
        "spectral_centroid": round(centroid, 2),
        "band_energies": [round(value, 4) for value in band_energies],
        "low_mid_high_ratio": [round(low, 4), round(mid, 4), round(high, 4)],
        "onset_count": onset_count,
        "tempo_bpm": round(tempo_bpm, 2),
    }
