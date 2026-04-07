from __future__ import annotations

import math


def compute_band_energies(samples: list[float], band_count: int = 16) -> list[float]:
    """Returns placeholder band energies until a real FFT backend is wired in."""
    if not samples or band_count <= 0:
        return [0.0] * max(band_count, 0)

    chunk_size = max(len(samples) // band_count, 1)
    bands: list[float] = []

    for index in range(band_count):
        start = index * chunk_size
        end = min(start + chunk_size, len(samples))
        chunk = samples[start:end]
        if not chunk:
            bands.append(0.0)
            continue
        energy = math.sqrt(sum(sample * sample for sample in chunk) / len(chunk))
        bands.append(energy)

    return bands
