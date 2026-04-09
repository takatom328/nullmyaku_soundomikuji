import json
import logging
from urllib import error, request

from ..utils.config import AIConfig


class AIClient:
    """Omikuji text generator with local/cloud/hybrid modes."""

    def __init__(self, config: AIConfig) -> None:
        self.config = config
        self._logger = logging.getLogger(__name__)
        self._last_generation = {
            "mode": (self.config.mode or "local").lower(),
            "provider": "local",
            "fallback_used": False,
            "error": None,
        }

    def build_payload(
        self,
        audio_features,
        imu_features,
        state,
        transcript,
    ):
        return {
            "model": self.config.model,
            "mode": (self.config.mode or "local").lower(),
            "audio_features": audio_features,
            "imu_features": imu_features,
            "derived_state": state,
            "transcript": transcript,
        }

    def status(self):
        return dict(self._last_generation)

    def _generate_local_omikuji(self, state):
        current_state = state["state"]
        interaction_mode = state.get("interaction_mode", "listening")
        motion_pattern = state.get("motion_pattern", "swaying")
        voice_texture = state.get("voice_texture", "neutral")
        sync = float(state.get("audio_motion_sync", 0.0))

        if sync > 0.7:
            key_line = "声と身体が同じリズムを刻んでいます。"
        elif sync > 0.4:
            key_line = "声と動きが少しずつ噛み合い始めています。"
        else:
            key_line = "まずは身体のテンポを先に決めると道が開きます。"

        return (
            f"あなたの今の状態は {current_state} です。\n"
            f"音の質感は {voice_texture}、動きは {motion_pattern}、対話モードは {interaction_mode}。\n"
            f"{key_line}\n"
            "迷いよりも、最初の一歩を信じてください。"
        )

    def _build_cloud_request_body(self, payload):
        mode = payload.get("mode", "local")
        summary = {
            "state": payload.get("derived_state", {}).get("state"),
            "state_source": payload.get("derived_state", {}).get("state_source"),
            "energy": payload.get("derived_state", {}).get("energy"),
            "brightness": payload.get("derived_state", {}).get("brightness"),
            "rhythm_stability": payload.get("derived_state", {}).get("rhythm_stability"),
            "motion_drive": payload.get("derived_state", {}).get("motion_drive"),
            "audio_motion_sync": payload.get("derived_state", {}).get("audio_motion_sync"),
            "audio_features": payload.get("audio_features"),
            "imu_features": payload.get("imu_features"),
            "transcript": payload.get("transcript"),
        }
        return {
            "model": payload.get("model"),
            "input": [
                {
                    "role": "system",
                    "content": (
                        "あなたはインタラクティブ作品のための短文おみくじ生成アシスタントです。"
                        "入力JSONを解釈し、2-4文の日本語で詩的かつ具体的に返答してください。"
                        "出力はプレーンテキストのみ。"
                    ),
                },
                {
                    "role": "user",
                    "content": "状態JSON:\n" + json.dumps(summary, ensure_ascii=False),
                },
                {
                    "role": "user",
                    "content": "mode: {mode}".format(mode=mode),
                },
            ],
        }

    def _extract_response_text(self, response_json):
        output_text = response_json.get("output_text")
        if output_text:
            return str(output_text).strip()

        output = response_json.get("output", [])
        if not isinstance(output, list):
            return ""

        texts = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content", [])
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") in ("output_text", "text"):
                    text = part.get("text")
                    if text:
                        texts.append(str(text))
        return "\n".join(texts).strip()

    def _generate_cloud_omikuji(self, payload):
        if not self.config.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        if self.config.endpoint != "responses":
            raise RuntimeError("Unsupported AI endpoint: {0}".format(self.config.endpoint))

        base = self.config.base_url.rstrip("/")
        endpoint_url = base + "/responses"
        body = self._build_cloud_request_body(payload)
        body_bytes = json.dumps(body, ensure_ascii=False).encode("utf-8")

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": "Bearer {0}".format(self.config.api_key),
        }
        http_request = request.Request(
            endpoint_url,
            data=body_bytes,
            headers=headers,
            method="POST",
        )

        try:
            with request.urlopen(http_request, timeout=self.config.timeout_sec) as response:
                raw = response.read().decode("utf-8")
                response_json = json.loads(raw)
        except error.URLError as exc:
            raise RuntimeError("Cloud request failed: {0}".format(exc)) from exc

        text = self._extract_response_text(response_json)
        if not text:
            raise RuntimeError("Cloud response returned no text")
        return text

    def generate_omikuji(
        self,
        audio_features,
        imu_features,
        state,
        transcript,
    ) -> str:
        payload = self.build_payload(audio_features, imu_features, state, transcript)
        mode = (self.config.mode or "local").lower()
        wants_cloud = mode in ("cloud", "hybrid")

        if wants_cloud:
            try:
                text = self._generate_cloud_omikuji(payload)
                self._last_generation = {
                    "mode": mode,
                    "provider": "cloud",
                    "fallback_used": False,
                    "error": None,
                }
                return text
            except Exception as exc:
                self._logger.warning("Cloud omikuji generation failed: %s", exc)
                if mode == "cloud" and not self.config.fallback_enabled:
                    raise

                text = self._generate_local_omikuji(state)
                self._last_generation = {
                    "mode": mode,
                    "provider": "local",
                    "fallback_used": True,
                    "error": str(exc),
                }
                return text

        text = self._generate_local_omikuji(state)
        self._last_generation = {
            "mode": mode,
            "provider": "local",
            "fallback_used": False,
            "error": None,
        }
        return text
