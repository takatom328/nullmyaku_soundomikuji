import math
import json
from pathlib import Path

from ..utils.config import LocalModelConfig


def _softmax(logits):
    if not logits:
        return []
    max_logit = max(logits)
    exps = [math.exp(value - max_logit) for value in logits]
    total = sum(exps) or 1.0
    return [value / total for value in exps]


class LocalModelRunner:
    def __init__(self, config: LocalModelConfig, logger) -> None:
        self.config = config
        self.logger = logger
        self.backend = (self.config.backend or "prototype").lower()
        self.enabled = True
        self.input_name = None
        self.output_name = None
        self.session = None
        self.centroid_model = None
        self.labels = [
            label.strip()
            for label in (self.config.labels or "").split(",")
            if label.strip()
        ]
        if not self.labels:
            self.labels = ["energetic", "delicate", "focused", "resonant", "open", "unstable"]
        self.last_error = None

        if self.backend == "onnx":
            self._init_onnx()
        elif self.backend == "centroid":
            self._init_centroid()
        elif self.backend not in ("prototype", "none"):
            self.enabled = False
            self.last_error = "Unsupported local model backend: {0}".format(self.backend)
            self.logger.warning(self.last_error)

    def _init_onnx(self):
        model_path = (self.config.model_path or "").strip()
        if not model_path:
            self.enabled = False
            self.last_error = "LOCAL_MODEL_PATH is empty"
            self.logger.warning(self.last_error)
            return

        resolved_path = Path(model_path).expanduser()
        if not resolved_path.is_file():
            self.enabled = False
            self.last_error = "Local ONNX model not found: {0}".format(resolved_path)
            self.logger.warning(self.last_error)
            return

        try:
            import onnxruntime as ort
        except Exception as exc:
            self.enabled = False
            self.last_error = "onnxruntime import failed: {0}".format(exc)
            self.logger.warning(self.last_error)
            return

        try:
            self.session = ort.InferenceSession(str(resolved_path))
            self.input_name = self.session.get_inputs()[0].name
            outputs = self.session.get_outputs()
            self.output_name = outputs[0].name if outputs else None
            self.logger.info("Local ONNX model loaded: %s", resolved_path)
        except Exception as exc:
            self.enabled = False
            self.last_error = "Failed to initialize ONNX session: {0}".format(exc)
            self.logger.warning(self.last_error)

    def _init_centroid(self):
        model_path = (self.config.model_path or "").strip()
        if not model_path:
            self.enabled = False
            self.last_error = "LOCAL_MODEL_PATH is empty"
            self.logger.warning(self.last_error)
            return

        resolved_path = Path(model_path).expanduser()
        if not resolved_path.is_file():
            self.enabled = False
            self.last_error = "Local centroid model not found: {0}".format(resolved_path)
            self.logger.warning(self.last_error)
            return

        try:
            payload = json.loads(resolved_path.read_text(encoding="utf-8"))
        except Exception as exc:
            self.enabled = False
            self.last_error = "Failed to load centroid model JSON: {0}".format(exc)
            self.logger.warning(self.last_error)
            return

        labels = payload.get("labels", [])
        centroids = payload.get("centroids", {})
        feature_mean = payload.get("feature_mean", [])
        feature_std = payload.get("feature_std", [])
        feature_size = int(payload.get("feature_size", 0))

        if not labels or not isinstance(centroids, dict) or feature_size <= 0:
            self.enabled = False
            self.last_error = "Centroid model JSON is missing required keys"
            self.logger.warning(self.last_error)
            return

        for label in labels:
            vector = centroids.get(label)
            if not isinstance(vector, list) or len(vector) != feature_size:
                self.enabled = False
                self.last_error = "Centroid vector shape mismatch for label {0}".format(
                    label
                )
                self.logger.warning(self.last_error)
                return

        if len(feature_mean) != feature_size or len(feature_std) != feature_size:
            self.enabled = False
            self.last_error = "Centroid model normalization shape mismatch"
            self.logger.warning(self.last_error)
            return

        self.centroid_model = {
            "labels": [str(label) for label in labels],
            "centroids": centroids,
            "feature_mean": [float(value) for value in feature_mean],
            "feature_std": [float(value) for value in feature_std],
            "feature_size": feature_size,
        }
        self.labels = list(self.centroid_model["labels"])
        self.logger.info("Local centroid model loaded: %s", resolved_path)

    def _classify_centroid(self, fusion_embedding):
        model = self.centroid_model
        if model is None:
            return None

        feature_size = model["feature_size"]
        input_vector = [float(value) for value in fusion_embedding[:feature_size]]
        if len(input_vector) < feature_size:
            input_vector.extend([0.0] * (feature_size - len(input_vector)))

        normalized = []
        for index in range(feature_size):
            denom = model["feature_std"][index]
            if abs(denom) < 1e-9:
                denom = 1.0
            normalized.append((input_vector[index] - model["feature_mean"][index]) / denom)

        similarities = []
        for label in model["labels"]:
            centroid = model["centroids"][label]
            dot = sum(left * right for left, right in zip(normalized, centroid))
            norm_a = math.sqrt(sum(value * value for value in normalized))
            norm_b = math.sqrt(sum(value * value for value in centroid))
            if norm_a <= 1e-9 or norm_b <= 1e-9:
                similarity = 0.0
            else:
                similarity = dot / (norm_a * norm_b)
            similarities.append(similarity)

        probs = _softmax([value * 4.0 for value in similarities])
        if not probs:
            return None

        best_index = max(range(len(probs)), key=lambda index: probs[index])
        best_label = model["labels"][best_index]
        score_map = {}
        for index, prob in enumerate(probs):
            score_map[model["labels"][index]] = round(float(prob), 4)
        return {
            "state": best_label,
            "confidence": round(float(probs[best_index]), 4),
            "scores": score_map,
            "source": "centroid",
        }

    def status(self):
        return {
            "backend": self.backend,
            "enabled": self.enabled,
            "labels": self.labels,
            "last_error": self.last_error,
            "confidence_threshold": self.config.confidence_threshold,
        }

    def classify(self, fusion_embedding):
        if self.backend == "centroid":
            if not self.enabled:
                return None
            return self._classify_centroid(fusion_embedding)

        if self.backend != "onnx" or not self.enabled or self.session is None:
            return None

        try:
            import numpy as np
        except Exception:
            self.enabled = False
            self.last_error = "numpy is required for onnx backend"
            return None

        try:
            input_array = np.array([fusion_embedding], dtype=np.float32)
            outputs = self.session.run([self.output_name], {self.input_name: input_array})
            logits = outputs[0][0].tolist()
            probs = _softmax(logits)
            if not probs:
                return None

            best_index = max(range(len(probs)), key=lambda index: probs[index])
            best_label = (
                self.labels[best_index]
                if best_index < len(self.labels)
                else "unstable"
            )
            score_map = {}
            for index, prob in enumerate(probs):
                if index < len(self.labels):
                    score_map[self.labels[index]] = round(float(prob), 4)
            return {
                "state": best_label,
                "confidence": round(float(probs[best_index]), 4),
                "scores": score_map,
                "source": "onnx",
            }
        except Exception as exc:
            self.last_error = "ONNX inference failed: {0}".format(exc)
            self.logger.warning(self.last_error)
            return None
