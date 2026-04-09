import math
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

    def status(self):
        return {
            "backend": self.backend,
            "enabled": self.enabled,
            "labels": self.labels,
            "last_error": self.last_error,
            "confidence_threshold": self.config.confidence_threshold,
        }

    def classify(self, fusion_embedding):
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
