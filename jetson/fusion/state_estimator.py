from .local_inference import (
    build_audio_embedding,
    build_imu_embedding,
    classify_fused_embedding,
    fuse_embeddings,
)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _label_voice_texture(brightness, zero_crossing_rate):
    if brightness > 0.75 or zero_crossing_rate > 0.08:
        return "bright"
    if brightness < 0.35 and zero_crossing_rate < 0.04:
        return "warm"
    return "neutral"


def _label_motion_pattern(movement_intensity, movement_frequency_hz):
    if movement_intensity > 0.45 and movement_frequency_hz > 1.7:
        return "driving"
    if movement_intensity < 0.15 and movement_frequency_hz < 0.7:
        return "still"
    return "swaying"


def _label_interaction_mode(audio_motion_sync, movement_intensity, rhythm_stability):
    if audio_motion_sync > 0.7 and movement_intensity > 0.25:
        return "entrained"
    if rhythm_stability > 0.7 and movement_intensity < 0.2:
        return "focused"
    if movement_intensity > 0.45:
        return "explorative"
    return "listening"


def estimate_state(
    audio_features,
    imu_features,
    model_runner=None,
    confidence_threshold=0.64,
):
    rms = float(audio_features.get("rms", 0.0))
    centroid = float(audio_features.get("spectral_centroid", 0.0))
    tempo = float(audio_features.get("tempo_bpm", 0.0))
    tempo_confidence = float(audio_features.get("tempo_confidence", 0.0))
    onset_count = float(audio_features.get("onset_count", 0.0))
    zero_crossing_rate = float(audio_features.get("zero_crossing_rate", 0.0))

    movement = float(imu_features.get("movement_intensity", 0.0))
    movement_frequency_hz = float(imu_features.get("movement_frequency_hz", 0.0))
    imu_rhythm_hz = float(imu_features.get("rhythm_hz", 0.0))
    imu_rhythm_stability = float(imu_features.get("rhythm_stability", 0.0))
    mean_acc_norm = float(imu_features.get("mean_acc_norm", 0.0))

    energy = _clamp((rms * 1.8) + (movement * 0.7))
    brightness = _clamp(centroid / 4000.0)
    audio_rhythm_stability = _clamp(1.0 - abs(tempo - 96.0) / 96.0) if tempo > 0 else 0.0
    audio_rhythm_stability *= _clamp(tempo_confidence if tempo_confidence > 0 else 0.3)
    if imu_rhythm_stability > 0 and audio_rhythm_stability > 0:
        rhythm_stability = _clamp((audio_rhythm_stability * 0.45) + (imu_rhythm_stability * 0.55))
    elif imu_rhythm_stability > 0:
        rhythm_stability = _clamp(imu_rhythm_stability)
    else:
        rhythm_stability = _clamp(audio_rhythm_stability)
    movement_intensity = _clamp(movement)
    motion_drive = _clamp((movement_intensity * 0.7) + (movement_frequency_hz / 3.0))

    movement_bpm = (imu_rhythm_hz if imu_rhythm_hz > 0 else movement_frequency_hz) * 60.0
    tempo_gap = abs(tempo - movement_bpm)
    if tempo > 0 and movement_bpm > 0:
        sync_by_tempo = _clamp(1.0 - (tempo_gap / 120.0))
    else:
        sync_by_tempo = 0.0
    sync_by_activity = _clamp((onset_count / 6.0) * (movement_intensity + 0.1))
    audio_motion_sync = _clamp((sync_by_tempo * 0.7) + (sync_by_activity * 0.3))

    vocal_presence = _clamp((rms * 2.4) + (onset_count / 12.0))
    grounding = _clamp(1.0 - abs(mean_acc_norm - 1.0) * 2.0)

    voice_texture = _label_voice_texture(brightness, zero_crossing_rate)
    motion_pattern = _label_motion_pattern(movement_intensity, movement_frequency_hz)
    interaction_mode = _label_interaction_mode(
        audio_motion_sync,
        movement_intensity,
        rhythm_stability,
    )

    if energy > 0.7 and movement_intensity > 0.5:
        state = "energetic"
    elif brightness > 0.6 and energy < 0.35:
        state = "delicate"
    elif rhythm_stability > 0.7 and movement_intensity < 0.3:
        state = "focused"
    elif audio_motion_sync > 0.7:
        state = "resonant"
    elif movement_intensity > 0.4:
        state = "open"
    else:
        state = "unstable"

    interpretation = (
        "voice={voice}, motion={motion}, mode={mode}".format(
            voice=voice_texture,
            motion=motion_pattern,
            mode=interaction_mode,
        )
    )

    audio_embedding = build_audio_embedding(audio_features)
    imu_embedding = build_imu_embedding(imu_features)
    fusion_embedding = fuse_embeddings(audio_embedding, imu_embedding)
    runner_result = None
    if model_runner is not None:
        runner_result = model_runner.classify(fusion_embedding)

    if runner_result is not None:
        embedded_state = runner_result["state"]
        embedded_confidence = float(runner_result["confidence"])
        embedded_scores = runner_result["scores"]
        embedded_source = runner_result.get("source", "onnx")
    else:
        embedded_state, embedded_confidence, embedded_scores = classify_fused_embedding(
            fusion_embedding
        )
        embedded_source = "prototype"

    state_source = "rules"
    if embedded_confidence >= float(confidence_threshold):
        state = embedded_state
        state_source = "embedding"

    return {
        "energy": round(energy, 4),
        "brightness": round(brightness, 4),
        "rhythm_stability": round(rhythm_stability, 4),
        "movement_intensity": round(movement_intensity, 4),
        "audio_rhythm_stability": round(audio_rhythm_stability, 4),
        "tempo_confidence": round(tempo_confidence, 4),
        "imu_rhythm_hz": round(imu_rhythm_hz, 4),
        "imu_rhythm_stability": round(imu_rhythm_stability, 4),
        "motion_drive": round(motion_drive, 4),
        "audio_motion_sync": round(audio_motion_sync, 4),
        "vocal_presence": round(vocal_presence, 4),
        "grounding": round(grounding, 4),
        "voice_texture": voice_texture,
        "motion_pattern": motion_pattern,
        "interaction_mode": interaction_mode,
        "interpretation": interpretation,
        "embedded_state": embedded_state,
        "embedded_state_confidence": round(embedded_confidence, 4),
        "embedded_state_scores": embedded_scores,
        "embedded_state_source": embedded_source,
        "state_source": state_source,
        "audio_embedding": [round(value, 4) for value in audio_embedding],
        "imu_embedding": [round(value, 4) for value in imu_embedding],
        "fusion_embedding": [round(value, 4) for value in fusion_embedding],
        "state": state,
    }
