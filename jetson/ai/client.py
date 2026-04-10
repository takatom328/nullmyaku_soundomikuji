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
        expo_recommendation=None,
    ):
        return {
            "model": self.config.model,
            "mode": (self.config.mode or "local").lower(),
            "audio_features": audio_features,
            "imu_features": imu_features,
            "derived_state": state,
            "transcript": transcript,
            "expo_recommendation": expo_recommendation or {},
        }

    def status(self):
        return dict(self._last_generation)

    def _generate_local_omikuji(self, state, expo_recommendation=None):
        current_state = state["state"]
        interaction_mode = state.get("interaction_mode", "listening")
        motion_pattern = state.get("motion_pattern", "swaying")
        voice_texture = state.get("voice_texture", "neutral")
        sync = float(state.get("audio_motion_sync", 0.0))
        expo = expo_recommendation or {}
        pavilion = str(expo.get("pavilion", "")).strip()
        cuisine = str(expo.get("cuisine", "")).strip()
        travel = str(expo.get("travel", "")).strip()

        if sync > 0.7:
            key_line = "声と身体が同じリズムを刻んでいます。"
        elif sync > 0.4:
            key_line = "声と動きが少しずつ噛み合い始めています。"
        else:
            key_line = "まずは身体のテンポを先に決めると道が開きます。"

        expo_line = ""
        if pavilion or cuisine or travel:
            expo_line = "万博では {0}、食は {1}、次の旅先は {2} が今日の相性です。\n".format(
                pavilion or "注目パビリオン",
                cuisine or "おすすめ料理",
                travel or "おすすめ旅先",
            )

        return (
            f"あなたの今の状態は {current_state} です。\n"
            f"音の質感は {voice_texture}、動きは {motion_pattern}、対話モードは {interaction_mode}。\n"
            f"{key_line}\n"
            f"{expo_line}"
            "迷いよりも、最初の一歩を信じてください。"
        )

    def _cloud_system_prompt(self):
        min_chars = max(60, int(self.config.min_chars))
        max_chars = max(min_chars, int(self.config.max_chars))
        return (
            "あなたは展示作品の語り手です。\n"
            "作品コンテキスト: {0}\n"
            "入力された状態JSONから、来場者の今の気配を短く解釈し、紙に印刷される文面を作成してください。\n"
            "文体: {1}\n"
            "断定的な診断・医療/法律/投資助言・人格否定はしないこと。\n"
            "出力ルール:\n"
            "1) 3-4文のみ\n"
            "2) 各文は短め（全体{2}-{3}文字目安）\n"
            "3) 最低1つ、行動しやすい具体表現を入れる\n"
            "4) 最終文は前向きな結びにする\n"
            "5) expo_recommendation がある場合、少なくとも1文で万博の楽しみ方として自然に取り入れる\n"
            "6) プレーンテキストのみ（JSONや見出しは不要）"
        ).format(
            self.config.narrative_context,
            self.config.tone,
            min_chars,
            max_chars,
        )

    def _cloud_style_guide(self):
        return (
            "スタイル指針:\n"
            "- 1文目: 現在の空気感を言語化\n"
            "- 2文目: 音と動きの関係を示す\n"
            "- 3文目: 今日の鍵となる小さな行動\n"
            "- 4文目: 希望で締める（必要な場合のみ）\n"
            "- 抽象語だけで終わらず、手触りのある語を1つ入れる"
        )

    def _cloud_few_shot_examples(self):
        return [
            {
                "input": {
                    "state": "focused",
                    "energy": 0.31,
                    "brightness": 0.48,
                    "audio_motion_sync": 0.66,
                    "motion_drive": 0.29,
                    "voice_texture": "warm",
                    "motion_pattern": "still",
                    "interaction_mode": "focused",
                },
                "output": (
                    "今のあなたは、静かな集中の層に入っています。\n"
                    "声の温度と身体の揺れが、無理なく同じ速度を選びはじめています。\n"
                    "今日は作業の最初の5分だけ、迷わず手を動かしてみてください。\n"
                    "小さな開始が、そのまま流れになります。"
                ),
            },
            {
                "input": {
                    "state": "energetic",
                    "energy": 0.82,
                    "brightness": 0.57,
                    "audio_motion_sync": 0.74,
                    "motion_drive": 0.79,
                    "voice_texture": "bright",
                    "motion_pattern": "driving",
                    "interaction_mode": "entrained",
                },
                "output": (
                    "あなたの内側では、すでに前進の合図が鳴っています。\n"
                    "音の勢いと身体のリズムが揃い、追い風の角度が見えています。\n"
                    "今日は決めきれない候補を一つに絞り、最初の一手を先に打ってください。\n"
                    "勢いは、使った瞬間に味方になります。"
                ),
            },
            {
                "input": {
                    "state": "delicate",
                    "energy": 0.24,
                    "brightness": 0.81,
                    "audio_motion_sync": 0.33,
                    "motion_drive": 0.19,
                    "voice_texture": "bright",
                    "motion_pattern": "swaying",
                    "interaction_mode": "listening",
                },
                "output": (
                    "今のあなたは、感覚の輪郭が細く澄んでいます。\n"
                    "音は先に遠くを照らし、身体はそれを慎重に追いかけています。\n"
                    "今日は予定を一つ減らし、その分だけ呼吸の深さを選んでください。\n"
                    "余白ができるほど、次の兆しは見つけやすくなります。"
                ),
            },
        ]

    def _render_few_shot_prompt(self):
        blocks = ["例文（スタイル参考）:"]
        examples = self._cloud_few_shot_examples()
        for index, example in enumerate(examples, start=1):
            blocks.append(
                "Example {0} Input:\n{1}".format(
                    index, json.dumps(example["input"], ensure_ascii=False)
                )
            )
            blocks.append("Example {0} Output:\n{1}".format(index, example["output"]))
        return "\n\n".join(blocks)

    def _build_cloud_request_body(self, payload):
        mode = payload.get("mode", "local")
        derived_state = payload.get("derived_state", {})
        summary = {
            "project_context": {
                "title": self.config.narrative_context,
                "output_medium": "thermal_printer",
                "audience": "展示来場者",
                "prompt_profile": self.config.prompt_profile,
            },
            "state": derived_state.get("state"),
            "state_source": derived_state.get("state_source"),
            "energy": derived_state.get("energy"),
            "brightness": derived_state.get("brightness"),
            "rhythm_stability": derived_state.get("rhythm_stability"),
            "motion_drive": derived_state.get("motion_drive"),
            "audio_motion_sync": derived_state.get("audio_motion_sync"),
            "voice_texture": derived_state.get("voice_texture"),
            "motion_pattern": derived_state.get("motion_pattern"),
            "interaction_mode": derived_state.get("interaction_mode"),
            "audio_features": payload.get("audio_features"),
            "imu_features": payload.get("imu_features"),
            "transcript": payload.get("transcript"),
            "expo_recommendation": payload.get("expo_recommendation"),
            "mode": mode,
        }
        return {
            "model": payload.get("model"),
            "input": [
                {
                    "role": "system",
                    "content": self._cloud_system_prompt(),
                },
                {
                    "role": "user",
                    "content": self._cloud_style_guide(),
                },
                {
                    "role": "user",
                    "content": self._render_few_shot_prompt(),
                },
                {
                    "role": "user",
                    "content": "今回の入力JSON:\n" + json.dumps(summary, ensure_ascii=False),
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
        expo_recommendation=None,
    ) -> str:
        payload = self.build_payload(
            audio_features,
            imu_features,
            state,
            transcript,
            expo_recommendation=expo_recommendation,
        )
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

                text = self._generate_local_omikuji(
                    state, expo_recommendation=expo_recommendation
                )
                self._last_generation = {
                    "mode": mode,
                    "provider": "local",
                    "fallback_used": True,
                    "error": str(exc),
                }
                return text

        text = self._generate_local_omikuji(
            state, expo_recommendation=expo_recommendation
        )
        self._last_generation = {
            "mode": mode,
            "provider": "local",
            "fallback_used": False,
            "error": None,
        }
        return text
