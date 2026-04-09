#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path


AUDIO_KEYS = [
    "rms",
    "spectral_centroid",
    "tempo_bpm",
    "dominant_frequency_hz",
    "zero_crossing_rate",
    "onset_count",
]

IMU_KEYS = [
    "movement_intensity",
    "movement_frequency_hz",
    "rhythm_hz",
    "rhythm_stability",
    "mean_acc_norm",
    "peak_acc_norm",
    "sample_rate_hz",
    "peak_count",
]

STATE_KEYS = [
    "energy",
    "brightness",
    "rhythm_stability",
    "motion_drive",
    "audio_motion_sync",
    "vocal_presence",
    "grounding",
    "embedded_state_confidence",
]


def _to_float(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    try:
        return float(value)
    except Exception:
        return 0.0


def _extract_list(values, size):
    if not isinstance(values, list):
        return [0.0] * size
    result = [_to_float(value) for value in values[:size]]
    if len(result) < size:
        result.extend([0.0] * (size - len(result)))
    return result


def build_feature_row(payload):
    audio = payload.get("audio_features", {})
    imu = payload.get("imu_features", {})
    state = payload.get("state", {})

    feature_keys = []
    feature_values = []

    for key in AUDIO_KEYS:
        feature_keys.append("audio.{0}".format(key))
        feature_values.append(_to_float(audio.get(key, 0.0)))

    low_mid_high = _extract_list(audio.get("low_mid_high_ratio", []), 3)
    for index, value in enumerate(low_mid_high):
        feature_keys.append("audio.low_mid_high_ratio[{0}]".format(index))
        feature_values.append(value)

    band_energies = _extract_list(audio.get("band_energies", []), 16)
    for index, value in enumerate(band_energies):
        feature_keys.append("audio.band_energies[{0}]".format(index))
        feature_values.append(value)

    for key in IMU_KEYS:
        feature_keys.append("imu.{0}".format(key))
        feature_values.append(_to_float(imu.get(key, 0.0)))

    for key in STATE_KEYS:
        feature_keys.append("state.{0}".format(key))
        feature_values.append(_to_float(state.get(key, 0.0)))

    audio_embedding = _extract_list(state.get("audio_embedding", []), 8)
    imu_embedding = _extract_list(state.get("imu_embedding", []), 8)
    fusion_embedding = _extract_list(state.get("fusion_embedding", []), 12)

    for index, value in enumerate(audio_embedding):
        feature_keys.append("state.audio_embedding[{0}]".format(index))
        feature_values.append(value)
    for index, value in enumerate(imu_embedding):
        feature_keys.append("state.imu_embedding[{0}]".format(index))
        feature_values.append(value)
    for index, value in enumerate(fusion_embedding):
        feature_keys.append("state.fusion_embedding[{0}]".format(index))
        feature_values.append(value)

    return feature_keys, feature_values


def load_session(path):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def build_dataset(input_dir, output_dir):
    input_path = Path(input_dir).expanduser()
    output_path = Path(output_dir).expanduser()
    output_path.mkdir(parents=True, exist_ok=True)

    session_files = sorted(input_path.glob("*.json"))
    dataset_file = output_path / "session_dataset.jsonl"
    labels_file = output_path / "labels_template.csv"

    rows = []
    feature_keys = None

    for session_file in session_files:
        payload = load_session(session_file)
        if payload is None:
            continue

        keys, values = build_feature_row(payload)
        if feature_keys is None:
            feature_keys = keys
        meta = payload.get("meta", {})
        state = payload.get("state", {})
        row = {
            "session_file": session_file.name,
            "session_path": str(session_file),
            "session_id": str(meta.get("session_id", "")),
            "duration_sec": _to_float(meta.get("duration_sec", 0.0)),
            "stop_reason": str(meta.get("stop_reason", "")),
            "auto_label": str(state.get("state", "")),
            "manual_label": "",
            "state_source": str(state.get("state_source", "")),
            "feature_keys": keys,
            "feature_values": values,
        }
        rows.append(row)

    with dataset_file.open("w", encoding="utf-8") as dataset_stream:
        for row in rows:
            dataset_stream.write(json.dumps(row, ensure_ascii=False) + "\n")

    with labels_file.open("w", encoding="utf-8", newline="") as labels_stream:
        writer = csv.writer(labels_stream)
        writer.writerow(
            [
                "session_file",
                "session_id",
                "auto_label",
                "manual_label",
                "duration_sec",
                "stop_reason",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row["session_file"],
                    row["session_id"],
                    row["auto_label"],
                    row["manual_label"],
                    row["duration_sec"],
                    row["stop_reason"],
                ]
            )

    return {
        "input_dir": str(input_path),
        "output_dir": str(output_path),
        "session_count": len(rows),
        "feature_count": len(feature_keys or []),
        "dataset_file": str(dataset_file),
        "labels_file": str(labels_file),
    }


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build training dataset from session JSON files."
    )
    parser.add_argument(
        "--input-dir",
        default="sessions",
        help="Directory containing archived session JSON files.",
    )
    parser.add_argument(
        "--output-dir",
        default="training",
        help="Directory where dataset outputs will be written.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    summary = build_dataset(args.input_dir, args.output_dir)
    print(
        "Built dataset: sessions={0}, features={1}".format(
            summary["session_count"], summary["feature_count"]
        )
    )
    print("JSONL: {0}".format(summary["dataset_file"]))
    print("Labels CSV: {0}".format(summary["labels_file"]))


if __name__ == "__main__":
    main()
