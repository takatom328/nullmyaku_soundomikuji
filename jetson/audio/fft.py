import math


def _apply_hann_window(samples):
    if len(samples) <= 1:
        return samples[:]

    last_index = len(samples) - 1
    return [
        sample * (0.5 - 0.5 * math.cos((2.0 * math.pi * index) / last_index))
        for index, sample in enumerate(samples)
    ]


def compute_frequency_spectrum(
    samples,
    sample_rate_hz: int,
):
    """Computes a positive-frequency magnitude spectrum with a Hann window."""
    if not samples or sample_rate_hz <= 0:
        return [], []

    sample_count = len(samples)
    frequencies = [(sample_rate_hz * index) / sample_count for index in range(sample_count // 2 + 1)]

    if max(abs(sample) for sample in samples) == 0.0:
        return frequencies, [0.0] * len(frequencies)

    mean = sum(samples) / sample_count
    centered = [sample - mean for sample in samples]
    windowed = _apply_hann_window(centered)

    magnitudes = []
    for bin_index in range(sample_count // 2 + 1):
        real = 0.0
        imag = 0.0
        for sample_index, sample in enumerate(windowed):
            angle = (2.0 * math.pi * bin_index * sample_index) / sample_count
            real += sample * math.cos(angle)
            imag -= sample * math.sin(angle)
        magnitudes.append(math.sqrt(real * real + imag * imag))

    return frequencies, magnitudes


def compute_band_energies_from_spectrum(
    frequencies_hz,
    magnitudes,
    band_count: int = 16,
):
    if not frequencies_hz or not magnitudes or band_count <= 0:
        return [0.0] * max(band_count, 0)

    max_frequency_hz = frequencies_hz[-1] if frequencies_hz else 0.0
    if max_frequency_hz <= 0:
        return [0.0] * band_count

    band_width_hz = max_frequency_hz / band_count
    bands = [0.0] * band_count

    for frequency_hz, magnitude in zip(frequencies_hz[1:], magnitudes[1:]):
        band_index = min(int(frequency_hz / band_width_hz), band_count - 1)
        bands[band_index] += magnitude * magnitude

    return [math.sqrt(energy) for energy in bands]


def compute_band_energies(
    samples,
    sample_rate_hz: int,
    band_count: int = 16,
):
    frequencies_hz, magnitudes = compute_frequency_spectrum(samples, sample_rate_hz)
    return compute_band_energies_from_spectrum(
        frequencies_hz=frequencies_hz,
        magnitudes=magnitudes,
        band_count=band_count,
    )
