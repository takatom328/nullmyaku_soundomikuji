import math
import os

from .fft import compute_band_energies_from_spectrum, compute_frequency_spectrum
from .input import AudioFrame
from .rhythm import (
    TempoTracker,
    detect_onset_times,
    estimate_tempo_bpm,
    estimate_tempo_bpm_from_onsets,
)


_RHYTHM_TRACKER = None
_RHYTHM_TRACKER_SAMPLE_RATE = None
_RHYTHM_TRACKER_WINDOW_SEC = None
_LAST_LOW_BAND_ENERGY = 0.0


def _get_tracker(sample_rate_hz):
    global _RHYTHM_TRACKER
    global _RHYTHM_TRACKER_SAMPLE_RATE
    global _RHYTHM_TRACKER_WINDOW_SEC
    try:
        window_sec = float(os.getenv("AUDIO_TEMPO_WINDOW_SEC", "8.0"))
    except ValueError:
        window_sec = 8.0
    if window_sec < 2.0:
        window_sec = 2.0
    if (
        _RHYTHM_TRACKER is None
        or _RHYTHM_TRACKER_SAMPLE_RATE != int(sample_rate_hz)
        or _RHYTHM_TRACKER_WINDOW_SEC != window_sec
    ):
        _RHYTHM_TRACKER = TempoTracker(
            sample_rate_hz=sample_rate_hz,
            history_seconds=window_sec,
        )
        _RHYTHM_TRACKER_SAMPLE_RATE = int(sample_rate_hz)
        _RHYTHM_TRACKER_WINDOW_SEC = window_sec
    return _RHYTHM_TRACKER


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
    global _LAST_LOW_BAND_ENERGY
    samples = frame.samples
    if not samples or sample_rate_hz <= 0:
        return {
            "rms": 0.0,
            "spectral_centroid": 0.0,
            "band_energies": [0.0] * 16,
            "low_mid_high_ratio": [0.0, 0.0, 0.0],
            "onset_count": 0,
            "tempo_bpm": 0.0,
            "tempo_confidence": 0.0,
            "onset_rate_hz": 0.0,
            "beat_strength": 0.0,
            "beat_period_sec": 0.0,
            "beat_detected": 0.0,
            "low_band_flux": 0.0,
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
    low_band_energy = sum(band_energies[:4])
    low_band_flux = max(0.0, low_band_energy - _LAST_LOW_BAND_ENERGY)
    _LAST_LOW_BAND_ENERGY = low_band_energy

    duration_sec = len(samples) / sample_rate_hz
    onset_times = detect_onset_times(samples, sample_rate_hz)
    onset_count = len(onset_times)
    tempo_bpm = estimate_tempo_bpm_from_onsets(onset_times)
    if tempo_bpm == 0.0:
        tempo_bpm = estimate_tempo_bpm(onset_count, duration_sec)
    tracker = _get_tracker(sample_rate_hz)
    rhythm_summary = tracker.update(
        frame.timestamp, samples, beat_signal_hint=low_band_flux
    )
    tracked_tempo = float(rhythm_summary.get("tempo_bpm", 0.0))
    tracked_confidence = float(rhythm_summary.get("tempo_confidence", 0.0))
    if tracked_tempo > 0.0 and tracked_confidence >= 0.05:
        tempo_bpm = tracked_tempo

    zero_crossing_rate = _zero_crossing_rate(samples)

    return {
        "rms": round(rms, 4),
        "spectral_centroid": round(centroid, 2),
        "band_energies": [round(value, 4) for value in band_energies],
        "low_mid_high_ratio": [round(low, 4), round(mid, 4), round(high, 4)],
        "onset_count": onset_count,
        "tempo_bpm": round(tempo_bpm, 2),
        "tempo_confidence": round(tracked_confidence, 4),
        "onset_rate_hz": round(float(rhythm_summary.get("onset_rate_hz", 0.0)), 4),
        "beat_strength": round(float(rhythm_summary.get("beat_strength", 0.0)), 4),
        "beat_period_sec": round(float(rhythm_summary.get("beat_period_sec", 0.0)), 4),
        "beat_detected": round(float(rhythm_summary.get("beat_detected", 0.0)), 4),
        "low_band_flux": round(low_band_flux, 6),
        "dominant_frequency_hz": round(dominant_frequency_hz, 2),
        "zero_crossing_rate": round(zero_crossing_rate, 4),
    }
