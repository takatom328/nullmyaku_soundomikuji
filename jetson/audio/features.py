import math

from .fft import compute_band_energies_from_spectrum, compute_frequency_spectrum
from .input import AudioFrame
from .rhythm import detect_onset_times, estimate_tempo_bpm, estimate_tempo_bpm_from_onsets


def _zero_crossing_rate(samples):
    if len(samples) < 2:
        return 0.0

    zero_crossings = 0
    for previous, current in zip(samples, samples[1:]):
        if (previous <= 0.0 < current) or (previous >= 0.0 > current):
            zero_crossings += 1

    return zero_crossings / (len(samples) - 1)


def _spectral_centroid(frequencies_hz, magnitudes):
    weighted_magnitude = sum(frequency * magnitude for frequency, magnitude in zip(frequencies_hz, magnitudes))
    total_magnitude = sum(magnitudes)
    if total_magnitude <= 0:
        return 0.0
    return weighted_magnitude / total_magnitude


def _dominant_frequency_hz(frequencies_hz, magnitudes):
    if len(frequencies_hz) < 2 or len(magnitudes) < 2:
        return 0.0

    positive_bins = list(zip(frequencies_hz[1:], magnitudes[1:]))
    if not positive_bins:
        return 0.0

    frequency_hz, magnitude = max(positive_bins, key=lambda pair: pair[1])
    return frequency_hz if magnitude > 0 else 0.0


def compute_audio_features(frame: AudioFrame, sample_rate_hz: int):
    samples = frame.samples
    if not samples or sample_rate_hz <= 0:
        return {
            "rms": 0.0,
            "spectral_centroid": 0.0,
            "band_energies": [0.0] * 16,
            "low_mid_high_ratio": [0.0, 0.0, 0.0],
            "onset_count": 0,
            "tempo_bpm": 0.0,
            "dominant_frequency_hz": 0.0,
            "zero_crossing_rate": 0.0,
        }

    rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
    frequencies_hz, magnitudes = compute_frequency_spectrum(samples, sample_rate_hz)
    band_energies = compute_band_energies_from_spectrum(
        frequencies_hz=frequencies_hz,
        magnitudes=magnitudes,
        band_count=16,
    )
    total_energy = sum(band_energies) or 1.0
    centroid = _spectral_centroid(frequencies_hz, magnitudes)
    dominant_frequency_hz = _dominant_frequency_hz(frequencies_hz, magnitudes)

    low = sum(band_energies[:5]) / total_energy
    mid = sum(band_energies[5:11]) / total_energy
    high = sum(band_energies[11:]) / total_energy

    duration_sec = len(samples) / sample_rate_hz
    onset_times = detect_onset_times(samples, sample_rate_hz)
    onset_count = len(onset_times)
    tempo_bpm = estimate_tempo_bpm_from_onsets(onset_times)
    if tempo_bpm == 0.0:
        tempo_bpm = estimate_tempo_bpm(onset_count, duration_sec)
    zero_crossing_rate = _zero_crossing_rate(samples)

    return {
        "rms": round(rms, 4),
        "spectral_centroid": round(centroid, 2),
        "band_energies": [round(value, 4) for value in band_energies],
        "low_mid_high_ratio": [round(low, 4), round(mid, 4), round(high, 4)],
        "onset_count": onset_count,
        "tempo_bpm": round(tempo_bpm, 2),
        "dominant_frequency_hz": round(dominant_frequency_hz, 2),
        "zero_crossing_rate": round(zero_crossing_rate, 4),
    }
