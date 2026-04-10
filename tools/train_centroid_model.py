#!/usr/bin/env python3
import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def _to_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return float(default)


def _load_labels(labels_csv_path):
    labels = {}
    with labels_csv_path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            session_file = (row.get("session_file") or "").strip()
            if not session_file:
                continue
            manual = (row.get("manual_label") or "").strip()
            auto = (row.get("auto_label") or "").strip()
            labels[session_file] = {
                "manual_label": manual,
                "auto_label": auto,
            }
    return labels


def _load_dataset_rows(dataset_jsonl_path):
    rows = []
    with dataset_jsonl_path.open("r", encoding="utf-8") as stream:
        for raw in stream:
            line = raw.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _vector_norm(values):
    return sum(value * value for value in values) ** 0.5


def _fusion_indices(feature_keys):
    indices = []
    for index, key in enumerate(feature_keys):
        if str(key).startswith("state.fusion_embedding["):
            indices.append(index)
    return indices


def _extract_fusion_vector(row):
    keys = row.get("feature_keys", [])
    values = row.get("feature_values", [])
    if not isinstance(keys, list) or not isinstance(values, list):
        return None
    if len(keys) != len(values):
        return None

    indices = _fusion_indices(keys)
    if len(indices) != 12:
        return None
    vector = [_to_float(values[index]) for index in indices]
    if len(vector) != 12:
        return None
    return vector


def _compute_mean(vectors):
    if not vectors:
        return []
    size = len(vectors[0])
    acc = [0.0] * size
    for vector in vectors:
        for index, value in enumerate(vector):
            acc[index] += value
    return [value / len(vectors) for value in acc]


def _compute_std(vectors, mean):
    if not vectors:
        return []
    size = len(mean)
    acc = [0.0] * size
    for vector in vectors:
        for index, value in enumerate(vector):
            diff = value - mean[index]
            acc[index] += diff * diff
    std = [(value / len(vectors)) ** 0.5 for value in acc]
    return [value if value > 1e-6 else 1.0 for value in std]


def _z_normalize(vector, mean, std):
    return [(vector[index] - mean[index]) / std[index] for index in range(len(vector))]


def train_centroid_model(dataset_jsonl, labels_csv, output_path, use_auto_label):
    dataset_rows = _load_dataset_rows(dataset_jsonl)
    label_map = _load_labels(labels_csv)

    labeled_vectors = defaultdict(list)
    skipped_unlabeled = 0
    skipped_invalid = 0

    for row in dataset_rows:
        session_file = str(row.get("session_file", "")).strip()
        if not session_file:
            skipped_invalid += 1
            continue

        label_info = label_map.get(session_file, {})
        manual = (label_info.get("manual_label") or "").strip()
        auto = (label_info.get("auto_label") or "").strip()
        if manual:
            label = manual
        elif use_auto_label and auto:
            label = auto
        else:
            skipped_unlabeled += 1
            continue

        vector = _extract_fusion_vector(row)
        if vector is None:
            skipped_invalid += 1
            continue

        labeled_vectors[label].append(vector)

    labels = sorted(labeled_vectors.keys())
    if not labels:
        raise RuntimeError("No labeled samples found. Fill manual_label or enable auto label.")

    all_vectors = []
    for label in labels:
        all_vectors.extend(labeled_vectors[label])

    feature_mean = _compute_mean(all_vectors)
    feature_std = _compute_std(all_vectors, feature_mean)

    centroids = {}
    class_counts = {}
    for label in labels:
        normalized_vectors = [
            _z_normalize(vector, feature_mean, feature_std)
            for vector in labeled_vectors[label]
        ]
        centroid = _compute_mean(normalized_vectors)
        norm = _vector_norm(centroid)
        if norm > 1e-9:
            centroid = [value / norm for value in centroid]
        centroids[label] = [round(value, 8) for value in centroid]
        class_counts[label] = len(labeled_vectors[label])

    model_payload = {
        "schema_version": 1,
        "model_type": "centroid",
        "feature_type": "fusion_embedding_12d",
        "feature_size": len(feature_mean),
        "labels": labels,
        "class_counts": class_counts,
        "feature_mean": [round(value, 8) for value in feature_mean],
        "feature_std": [round(value, 8) for value in feature_std],
        "centroids": centroids,
        "trained_at": datetime.now().isoformat(),
        "notes": {
            "use_auto_label": bool(use_auto_label),
            "sample_count": len(all_vectors),
            "skipped_unlabeled": skipped_unlabeled,
            "skipped_invalid": skipped_invalid,
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(model_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return model_payload


def parse_args():
    parser = argparse.ArgumentParser(
        description="Train centroid classifier from session dataset."
    )
    parser.add_argument(
        "--dataset-jsonl",
        default="training/session_dataset.jsonl",
        help="Input dataset JSONL path.",
    )
    parser.add_argument(
        "--labels-csv",
        default="training/labels_template.csv",
        help="CSV with manual_label edits.",
    )
    parser.add_argument(
        "--output-model",
        default="models/local_centroid_model.json",
        help="Output model JSON path.",
    )
    parser.add_argument(
        "--use-auto-label",
        default="1",
        choices=["0", "1"],
        help="Use auto_label when manual_label is empty.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    dataset_path = Path(args.dataset_jsonl).expanduser()
    labels_path = Path(args.labels_csv).expanduser()
    output_path = Path(args.output_model).expanduser()
    use_auto_label = args.use_auto_label == "1"

    if not dataset_path.is_file():
        raise SystemExit("Dataset not found: {0}".format(dataset_path))
    if not labels_path.is_file():
        raise SystemExit("Labels CSV not found: {0}".format(labels_path))

    model = train_centroid_model(
        dataset_jsonl=dataset_path,
        labels_csv=labels_path,
        output_path=output_path,
        use_auto_label=use_auto_label,
    )

    sample_count = model["notes"]["sample_count"]
    label_count = len(model["labels"])
    print("Trained centroid model: samples={0}, labels={1}".format(sample_count, label_count))
    print("Model path: {0}".format(output_path))


if __name__ == "__main__":
    main()
