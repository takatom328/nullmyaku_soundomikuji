import math


def _clamp01(value):
    return max(0.0, min(1.0, float(value)))


def _normalize_vector(values):
    magnitude = math.sqrt(sum(value * value for value in values))
    if magnitude <= 1e-9:
        return [0.0 for _ in values]
    return [value / magnitude for value in values]


def build_audio_embedding(audio_features):
    ratios = audio_features.get("low_mid_high_ratio", [0.0, 0.0, 0.0])
    embedding = [
        _clamp01(audio_features.get("rms", 0.0) * 8.0),
        _clamp01(audio_features.get("spectral_centroid", 0.0) / 5000.0),
        _clamp01(audio_features.get("dominant_frequency_hz", 0.0) / 1200.0),
        _clamp01(audio_features.get("tempo_bpm", 0.0) / 180.0),
        _clamp01(audio_features.get("onset_count", 0.0) / 12.0),
        _clamp01(audio_features.get("zero_crossing_rate", 0.0) / 0.2),
        _clamp01(ratios[0] if len(ratios) > 0 else 0.0),
        _clamp01(ratios[2] if len(ratios) > 2 else 0.0),
    ]
    return _normalize_vector(embedding)


def build_imu_embedding(imu_features):
    embedding = [
        _clamp01(imu_features.get("movement_intensity", 0.0) / 1.2),
        _clamp01(imu_features.get("movement_frequency_hz", 0.0) / 4.0),
        _clamp01(imu_features.get("rhythm_hz", 0.0) / 4.0),
        _clamp01(imu_features.get("rhythm_stability", 0.0)),
        _clamp01(abs(imu_features.get("mean_acc_norm", 0.0) - 1.0)),
        _clamp01(imu_features.get("peak_acc_norm", 0.0) / 2.2),
        _clamp01(imu_features.get("sample_rate_hz", 0.0) / 100.0),
        _clamp01(imu_features.get("peak_count", 0.0) / 16.0),
    ]
    return _normalize_vector(embedding)


def fuse_embeddings(audio_embedding, imu_embedding):
    features = [
        audio_embedding[0],
        audio_embedding[1],
        audio_embedding[2],
        audio_embedding[3],
        imu_embedding[0],
        imu_embedding[1],
        imu_embedding[2],
        imu_embedding[3],
        audio_embedding[0] * imu_embedding[0],
        audio_embedding[3] * imu_embedding[2],
        abs(audio_embedding[1] - imu_embedding[0]),
        abs(audio_embedding[3] - imu_embedding[2]),
    ]
    return _normalize_vector(features)


_STATE_PROTOTYPES = {
    "energetic": [0.7, 0.4, 0.5, 0.5, 0.8, 0.7, 0.7, 0.5, 0.9, 0.8, 0.1, 0.2],
    "delicate": [0.3, 0.7, 0.3, 0.1, 0.2, 0.2, 0.2, 0.6, 0.2, 0.2, 0.6, 0.1],
    "focused": [0.4, 0.5, 0.3, 0.4, 0.2, 0.2, 0.6, 0.9, 0.2, 0.6, 0.4, 0.2],
    "resonant": [0.6, 0.5, 0.4, 0.7, 0.6, 0.6, 0.7, 0.7, 0.8, 0.9, 0.1, 0.1],
    "open": [0.5, 0.6, 0.5, 0.3, 0.7, 0.6, 0.5, 0.4, 0.7, 0.4, 0.2, 0.2],
    "unstable": [0.3, 0.2, 0.2, 0.1, 0.4, 0.2, 0.1, 0.2, 0.2, 0.1, 0.8, 0.8],
}

for _label in list(_STATE_PROTOTYPES):
    _STATE_PROTOTYPES[_label] = _normalize_vector(_STATE_PROTOTYPES[_label])


def _cosine_similarity(lhs, rhs):
    return sum(left * right for left, right in zip(lhs, rhs))


def classify_fused_embedding(fused_embedding):
    best_state = "unstable"
    best_score = -1.0
    all_scores = {}
    for state_name, prototype in _STATE_PROTOTYPES.items():
        score = _cosine_similarity(fused_embedding, prototype)
        all_scores[state_name] = round(score, 4)
        if score > best_score:
            best_state = state_name
            best_score = score

    confidence = _clamp01((best_score + 1.0) / 2.0)
    return best_state, confidence, all_scores
