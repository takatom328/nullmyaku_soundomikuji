from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import random
import shutil
import subprocess
import tempfile
from urllib import error, request
from uuid import uuid4

from ..utils.config import PrinterConfig


DEFAULT_JA_FONTS = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
]
TORII_TOKEN = "[[TORII]]"
TITLE_TOKEN_PREFIX = "[[TITLE:"
TITLE_TOKEN_SUFFIX = "]]"
FORTUNE_TOKEN_PREFIX = "[[FORTUNE:"
FORTUNE_TOKEN_SUFFIX = "]]"
QRCODE_TOKEN_PREFIX = "[[QRCODE:"
QRCODE_TOKEN_SUFFIX = "]]"
ALIGN_LEFT_TOKEN = "[[ALIGN_LEFT]]"
ALIGN_CENTER_TOKEN = "[[ALIGN_CENTER]]"

FORTUNE_WEIGHTS = [
    ("ミャクミャク大吉", 8),
    ("ぬるぬる中吉", 14),
    ("ﾇﾙﾇﾙ小吉", 18),
    ("ミャク吉", 20),
    ("こみゃく末吉", 18),
    ("null凶", 16),
    ("null2大凶", 6),
]

RECOMMENDED_CUISINES = [
    "イタリア: マルゲリータ",
    "タイ: トムヤムクン",
    "トルコ: ケバブ",
    "インド: バターチキン",
    "フランス: ガレット",
    "メキシコ: タコス",
    "ベトナム: フォー",
    "スペイン: パエリア",
]

EXPO_MOTIFS = [
    {
        "country": "イタリア",
        "feature": "創造性と職人技が重なり、丁寧な一手が作品になる気配",
        "pavilion": "イタリア館",
        "travel": "ミラノ",
    },
    {
        "country": "フランス",
        "feature": "美意識と構成力が際立ち、静かな洗練が流れを整える気配",
        "pavilion": "フランス館",
        "travel": "リヨン",
    },
    {
        "country": "サウジアラビア",
        "feature": "スケールの大きな挑戦に向かう推進力が高まる気配",
        "pavilion": "サウジアラビア館",
        "travel": "リヤド",
    },
    {
        "country": "シンガポール",
        "feature": "都市と自然を両立させるように、効率と余白が同時に育つ気配",
        "pavilion": "シンガポール館",
        "travel": "シンガポール市街",
    },
    {
        "country": "オーストラリア",
        "feature": "開放感のある判断が生まれ、動きながら最適解へ向かう気配",
        "pavilion": "オーストラリア館",
        "travel": "シドニー",
    },
    {
        "country": "UAE",
        "feature": "未来志向と実装力が噛み合い、次の展開が見えやすい気配",
        "pavilion": "UAE館",
        "travel": "ドバイ",
    },
    {
        "country": "オランダ",
        "feature": "循環と調和の発想が強まり、長く続く選択ができる気配",
        "pavilion": "オランダ館",
        "travel": "アムステルダム",
    },
    {
        "country": "日本",
        "feature": "繊細さと粘り強さが同居し、細部の積み重ねが力になる気配",
        "pavilion": "日本館",
        "travel": "金沢",
    },
]
_EXPO_MOTIFS_CACHE = None
_EXPO_CUISINES_CACHE = None
_EXPO_RESTAURANTS_CACHE = None
_LAST_EXPO_COUNTRY = None
_LAST_CUISINE = None
_LAST_RESTAURANT = None

ADVICE = [
    "朝の5分で予定を整理しましょう。",
    "今日は一つだけ丁寧にやり切ること。",
    "返事を一拍おいてからすると運気安定。",
    "足元を整えると心も整います。",
    "迷ったら基本に戻ると吉。",
    "疲れを感じたら早めの休息を。",
]


def _build_cups_cmd(printer_name, orientation):
    orientation_opt = []
    if orientation == "portrait":
        orientation_opt = ["-o", "orientation-requested=3"]
    elif orientation == "landscape":
        orientation_opt = ["-o", "orientation-requested=4"]

    lp_cmd = shutil.which("lp")
    if lp_cmd:
        return [lp_cmd, "-d", printer_name] + orientation_opt
    lpr_cmd = shutil.which("lpr")
    if lpr_cmd:
        return [lpr_cmd, "-P", printer_name] + orientation_opt
    return None


def _choose_font_path(font_path):
    if font_path and os.path.exists(font_path):
        return font_path
    for path in DEFAULT_JA_FONTS:
        if os.path.exists(path):
            return path
    return None


def _image_size_px(path):
    try:
        from PIL import Image
    except Exception:
        return None, None
    try:
        with Image.open(path) as image:
            width, height = image.size
            return int(width), int(height)
    except Exception:
        return None, None


def _pick_fortune():
    names = [name for name, _ in FORTUNE_WEIGHTS]
    weights = [weight for _, weight in FORTUNE_WEIGHTS]
    return random.choices(names, weights=weights, k=1)[0]


def _load_expo_motifs():
    global _EXPO_MOTIFS_CACHE
    if _EXPO_MOTIFS_CACHE is not None:
        return _EXPO_MOTIFS_CACHE

    default_path = Path(__file__).resolve().parents[2] / "docs" / "expo_catalog.json"
    config_path = os.getenv("EXPO_CATALOG_PATH", "").strip()
    catalog_path = Path(config_path).expanduser() if config_path else default_path

    motifs = []
    try:
        if catalog_path.is_file():
            payload = json.loads(catalog_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                items = payload.get("motifs", [])
            elif isinstance(payload, list):
                items = payload
            else:
                items = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                country = str(item.get("country", "")).strip()
                feature = str(item.get("feature", "")).strip()
                pavilion = str(item.get("pavilion", "")).strip()
                travel = str(item.get("travel", "")).strip()
                if country and feature and pavilion and travel:
                    motifs.append(
                        {
                            "country": country,
                            "feature": feature,
                            "pavilion": pavilion,
                            "travel": travel,
                        }
                    )
    except Exception:
        motifs = []

    if not motifs:
        motifs = list(EXPO_MOTIFS)
    _EXPO_MOTIFS_CACHE = motifs
    return motifs


def _load_expo_cuisines():
    global _EXPO_CUISINES_CACHE
    if _EXPO_CUISINES_CACHE is not None:
        return _EXPO_CUISINES_CACHE

    default_path = Path(__file__).resolve().parents[2] / "docs" / "expo_catalog.json"
    config_path = os.getenv("EXPO_CATALOG_PATH", "").strip()
    catalog_path = Path(config_path).expanduser() if config_path else default_path

    cuisines = []
    try:
        if catalog_path.is_file():
            payload = json.loads(catalog_path.read_text(encoding="utf-8"))
            items = payload.get("cuisines", []) if isinstance(payload, dict) else []
            for item in items:
                text = str(item).strip()
                if text:
                    cuisines.append(text)
    except Exception:
        cuisines = []

    if not cuisines:
        cuisines = list(RECOMMENDED_CUISINES)
    _EXPO_CUISINES_CACHE = cuisines
    return cuisines


def _load_expo_restaurants():
    global _EXPO_RESTAURANTS_CACHE
    if _EXPO_RESTAURANTS_CACHE is not None:
        return _EXPO_RESTAURANTS_CACHE

    default_path = Path(__file__).resolve().parents[2] / "docs" / "expo_catalog.json"
    config_path = os.getenv("EXPO_CATALOG_PATH", "").strip()
    catalog_path = Path(config_path).expanduser() if config_path else default_path

    restaurants = []
    try:
        if catalog_path.is_file():
            payload = json.loads(catalog_path.read_text(encoding="utf-8"))
            items = payload.get("restaurants", []) if isinstance(payload, dict) else []
            for item in items:
                text = str(item).strip()
                if text:
                    restaurants.append(text)
    except Exception:
        restaurants = []

    _EXPO_RESTAURANTS_CACHE = restaurants
    return restaurants


def _wrap_text_to_width(draw, text, font, max_width):
    wrapped = []
    for raw_line in text.splitlines() or [""]:
        stripped = raw_line.strip()
        if (
            stripped == TORII_TOKEN
            or (
                stripped.startswith(TITLE_TOKEN_PREFIX)
                and stripped.endswith(TITLE_TOKEN_SUFFIX)
            )
            or (
                stripped.startswith(FORTUNE_TOKEN_PREFIX)
                and stripped.endswith(FORTUNE_TOKEN_SUFFIX)
            )
            or (
                stripped.startswith(QRCODE_TOKEN_PREFIX)
                and stripped.endswith(QRCODE_TOKEN_SUFFIX)
            )
            or stripped in (ALIGN_LEFT_TOKEN, ALIGN_CENTER_TOKEN)
        ):
            wrapped.append(stripped)
            continue

        line = ""
        for ch in raw_line:
            candidate = line + ch
            if draw.textlength(candidate, font=font) <= max_width:
                line = candidate
            else:
                wrapped.append(line or ch)
                line = ch if draw.textlength(ch, font=font) <= max_width else ""
        wrapped.append(line)
    if text.endswith("\n"):
        wrapped.append("")
    return wrapped


def _render_text_horizontal_image_path(
    text,
    font_path,
    font_size,
    width_px,
    line_spacing,
    height_px,
    text_align,
):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return None

    resolved_font = _choose_font_path(font_path)
    margin = 16
    max_width = width_px - (margin * 2)
    text_align = (text_align or "center").lower()

    def _load_title_font(title_text, base_font_size, probe_draw):
        if not resolved_font:
            return ImageFont.load_default()
        max_size = max(base_font_size + 18, int(base_font_size * 2.1))
        min_size = max(16, base_font_size)
        for size in range(max_size, min_size - 1, -1):
            candidate = ImageFont.truetype(resolved_font, size)
            if probe_draw.textlength(title_text, font=candidate) <= (width_px - 24):
                return candidate
        return ImageFont.truetype(resolved_font, min_size)

    def _load_fortune_font(fortune_text, base_font_size, probe_draw):
        if not resolved_font:
            return ImageFont.load_default()
        max_size = max(base_font_size + 12, int(base_font_size * 1.7))
        min_size = max(18, base_font_size + 4)
        for size in range(max_size, min_size - 1, -1):
            candidate = ImageFont.truetype(resolved_font, size)
            if probe_draw.textlength(fortune_text, font=candidate) <= (width_px - 28):
                return candidate
        return ImageFont.truetype(resolved_font, min_size)

    def _layout_for_font_size(base_font_size):
        if resolved_font:
            base_font = ImageFont.truetype(resolved_font, base_font_size)
        else:
            base_font = ImageFont.load_default()

        probe = Image.new("L", (width_px, 100), color=255)
        probe_draw = ImageDraw.Draw(probe)
        lines = _wrap_text_to_width(probe_draw, text, base_font, max_width)
        ascent, descent = base_font.getmetrics()
        line_height = ascent + descent + line_spacing
        torii_height = max(96, line_height * 4)
        qr_size = min(220, max(140, int(width_px * 0.34)))

        total_height = margin * 2
        for line in lines:
            stripped = line.strip()
            if stripped in (ALIGN_LEFT_TOKEN, ALIGN_CENTER_TOKEN):
                continue
            if stripped == TORII_TOKEN:
                total_height += torii_height
            elif stripped.startswith(TITLE_TOKEN_PREFIX) and stripped.endswith(TITLE_TOKEN_SUFFIX):
                title_text = stripped[len(TITLE_TOKEN_PREFIX) : -len(TITLE_TOKEN_SUFFIX)]
                title_font = _load_title_font(title_text, base_font_size, probe_draw)
                ascent_t, descent_t = title_font.getmetrics()
                total_height += ascent_t + descent_t + line_spacing + 4
            elif stripped.startswith(FORTUNE_TOKEN_PREFIX) and stripped.endswith(
                FORTUNE_TOKEN_SUFFIX
            ):
                fortune_text = stripped[len(FORTUNE_TOKEN_PREFIX) : -len(FORTUNE_TOKEN_SUFFIX)]
                fortune_font = _load_fortune_font(fortune_text, base_font_size, probe_draw)
                ascent_f, descent_f = fortune_font.getmetrics()
                total_height += ascent_f + descent_f + line_spacing + 6
            elif stripped.startswith(QRCODE_TOKEN_PREFIX) and stripped.endswith(
                QRCODE_TOKEN_SUFFIX
            ):
                total_height += qr_size + line_spacing + 2
            else:
                total_height += line_height

        return {
            "font": base_font,
            "probe_draw": probe_draw,
            "lines": lines,
            "line_height": line_height,
            "torii_height": torii_height,
            "qr_size": qr_size,
            "total_height": total_height,
            "font_size": base_font_size,
        }

    chosen = _layout_for_font_size(font_size)
    min_height = 0
    if height_px and height_px > 0:
        min_height = int(height_px)
    render_height = max(240, min_height, chosen["total_height"])

    font = chosen["font"]
    probe_draw = chosen["probe_draw"]
    lines = chosen["lines"]
    line_height = chosen["line_height"]
    torii_height = chosen["torii_height"]
    qr_size = chosen["qr_size"]

    image = Image.new("L", (width_px, render_height), color=255)
    draw = ImageDraw.Draw(image)

    def _draw_torii(y):
        left = margin + int(max_width * 0.16)
        right = margin + int(max_width * 0.84)
        top1 = y + 6
        top2 = y + 22
        beam_h = 8
        draw.rectangle((left - 18, top1, right + 18, top1 + beam_h), fill=0)
        draw.rectangle((left, top2, right, top2 + beam_h), fill=0)

        post_w = 9
        post_top = top2 + beam_h + 4
        post_bottom = y + torii_height - 4
        left_post = margin + int(max_width * 0.32)
        right_post = margin + int(max_width * 0.68)
        draw.rectangle((left_post, post_top, left_post + post_w, post_bottom), fill=0)
        draw.rectangle((right_post, post_top, right_post + post_w, post_bottom), fill=0)
        return y + torii_height

    def _draw_qrcode(y, url):
        try:
            import qrcode
        except Exception:
            draw.text((margin, y), "QR: " + url, fill=0, font=font)
            return y + line_height * 2

        qr = qrcode.QRCode(
            border=1,
            box_size=6,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
        )
        qr.add_data(url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert("L")
        qr_img = qr_img.resize((qr_size, qr_size))
        x = int((width_px - qr_size) / 2)
        image.paste(qr_img, (x, y))
        return y + qr_size + line_spacing + 2

    y = margin
    current_align = text_align
    for line in lines:
        stripped = line.strip()
        if stripped == ALIGN_LEFT_TOKEN:
            current_align = "left"
            continue
        if stripped == ALIGN_CENTER_TOKEN:
            current_align = "center"
            continue
        if stripped == TORII_TOKEN:
            y = _draw_torii(y)
        elif stripped.startswith(TITLE_TOKEN_PREFIX) and stripped.endswith(TITLE_TOKEN_SUFFIX):
            title_text = stripped[len(TITLE_TOKEN_PREFIX) : -len(TITLE_TOKEN_SUFFIX)]
            title_font = _load_title_font(title_text, chosen["font_size"], probe_draw)
            tw = draw.textlength(title_text, font=title_font)
            tx = max(margin, int((width_px - tw) / 2))
            draw.text((tx, y), title_text, fill=0, font=title_font)
            ascent_t, descent_t = title_font.getmetrics()
            y += ascent_t + descent_t + line_spacing + 4
        elif stripped.startswith(FORTUNE_TOKEN_PREFIX) and stripped.endswith(
            FORTUNE_TOKEN_SUFFIX
        ):
            fortune_text = stripped[len(FORTUNE_TOKEN_PREFIX) : -len(FORTUNE_TOKEN_SUFFIX)]
            fortune_font = _load_fortune_font(
                fortune_text, chosen["font_size"], probe_draw
            )
            fw = draw.textlength(fortune_text, font=fortune_font)
            fx = max(margin, int((width_px - fw) / 2))
            draw.text((fx, y), fortune_text, fill=0, font=fortune_font)
            ascent_f, descent_f = fortune_font.getmetrics()
            y += ascent_f + descent_f + line_spacing + 6
        elif stripped.startswith(QRCODE_TOKEN_PREFIX) and stripped.endswith(
            QRCODE_TOKEN_SUFFIX
        ):
            url = stripped[len(QRCODE_TOKEN_PREFIX) : -len(QRCODE_TOKEN_SUFFIX)]
            y = _draw_qrcode(y, url)
        else:
            line_width = draw.textlength(line, font=font)
            if current_align == "left":
                x = margin
            else:
                x = max(margin, int((width_px - line_width) / 2))
            draw.text((x, y), line, fill=0, font=font)
            y += line_height

    tmp = tempfile.NamedTemporaryFile(prefix="omikuji_", suffix=".png", delete=False)
    tmp_path = tmp.name
    tmp.close()
    image.save(tmp_path, format="PNG")
    return tmp_path


def _render_text_vertical_image_path(
    text, font_path, font_size, width_px, height_px, line_spacing, column_spacing
):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return None

    resolved_font = _choose_font_path(font_path)
    if resolved_font:
        font = ImageFont.truetype(resolved_font, font_size)
    else:
        font = ImageFont.load_default()

    ascent, descent = font.getmetrics()
    row_height = ascent + descent + line_spacing
    col_width = font_size + column_spacing
    margin = 16
    usable_rows = max(1, (height_px - margin * 2) // row_height)

    columns = []
    for src_line in text.splitlines():
        if not src_line:
            columns.append("")
            continue
        chars = list(src_line)
        while chars:
            columns.append("".join(chars[:usable_rows]))
            chars = chars[usable_rows:]
        columns.append("")
    if not columns:
        columns = [""]

    usable_cols = max(1, (width_px - margin * 2) // col_width)
    columns = columns[-usable_cols:]

    image = Image.new("L", (width_px, height_px), color=255)
    draw = ImageDraw.Draw(image)
    x = width_px - margin - col_width
    for col in columns:
        y = margin
        for ch in col:
            draw.text((x, y), ch, fill=0, font=font)
            y += row_height
        x -= col_width
        if x < margin:
            break

    tmp = tempfile.NamedTemporaryFile(prefix="omikuji_", suffix=".png", delete=False)
    tmp_path = tmp.name
    tmp.close()
    image.save(tmp_path, format="PNG")
    return tmp_path


def _render_text_to_image_path(
    text,
    font_path,
    font_size,
    width_px,
    height_px,
    line_spacing,
    column_spacing,
    layout,
    text_align,
):
    if (layout or "horizontal").lower() == "vertical":
        return _render_text_vertical_image_path(
            text=text,
            font_path=font_path,
            font_size=font_size,
            width_px=width_px,
            height_px=height_px,
            line_spacing=line_spacing,
            column_spacing=column_spacing,
        )
    return _render_text_horizontal_image_path(
        text=text,
        font_path=font_path,
        font_size=font_size,
        width_px=width_px,
        line_spacing=line_spacing,
        height_px=height_px,
        text_align=text_align,
    )


def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _pick_expo_motif():
    global _LAST_EXPO_COUNTRY
    motifs = _load_expo_motifs()
    if not motifs:
        return {
            "country": "日本",
            "feature": "丁寧な積み重ねが未来につながる気配",
            "pavilion": "日本館",
            "travel": "大阪",
        }

    candidates = motifs
    if _LAST_EXPO_COUNTRY and len(motifs) > 1:
        filtered = [item for item in motifs if item.get("country") != _LAST_EXPO_COUNTRY]
        if filtered:
            candidates = filtered
    motif = random.choice(candidates)
    _LAST_EXPO_COUNTRY = motif.get("country")
    return motif


def _pick_recommended_cuisine():
    global _LAST_CUISINE
    cuisines = _load_expo_cuisines()
    if not cuisines:
        return random.choice(RECOMMENDED_CUISINES)
    candidates = cuisines
    if _LAST_CUISINE and len(cuisines) > 1:
        filtered = [item for item in cuisines if item != _LAST_CUISINE]
        if filtered:
            candidates = filtered
    picked = random.choice(candidates)
    _LAST_CUISINE = picked
    return picked


def _pick_recommended_restaurant():
    global _LAST_RESTAURANT
    restaurants = _load_expo_restaurants()
    if not restaurants:
        return ""
    candidates = restaurants
    if _LAST_RESTAURANT and len(restaurants) > 1:
        filtered = [item for item in restaurants if item != _LAST_RESTAURANT]
        if filtered:
            candidates = filtered
    picked = random.choice(candidates)
    _LAST_RESTAURANT = picked
    return picked


def _build_analysis_lines(audio_features, imu_features, state):
    tempo = _to_float(audio_features.get("tempo_bpm"), 0.0)
    tempo_conf = _to_float(audio_features.get("tempo_confidence"), 0.0)
    beat_strength = _to_float(audio_features.get("beat_strength"), 0.0)
    onset_rate_hz = _to_float(audio_features.get("onset_rate_hz"), 0.0)
    audio_sync = _to_float(state.get("audio_motion_sync"), 0.0)
    imu_rhythm_hz = _to_float(imu_features.get("rhythm_hz"), 0.0)
    movement_intensity = _to_float(imu_features.get("movement_intensity"), 0.0)
    return [
        "テンポ最大(BPM): {0:.2f}".format(tempo),
        "テンポ信頼度: {0:.3f}".format(tempo_conf),
        "ビート強度平均: {0:.3f}".format(beat_strength),
        "オンセット率(Hz): {0:.3f}".format(onset_rate_hz),
        "音×動作同期: {0:.3f}".format(audio_sync),
        "IMUリズム(Hz): {0:.3f}".format(imu_rhythm_hz),
        "動作強度平均: {0:.3f}".format(movement_intensity),
    ]


class Printer:
    """Sends print jobs to a Raspberry Pi print service or stdout."""

    def __init__(self, config: PrinterConfig) -> None:
        self.config = config
        self._logger = logging.getLogger(__name__)

    def format_ticket(
        self,
        state: str,
        message: str,
        audio_features=None,
        imu_features=None,
        state_features=None,
        expo_recommendation=None,
    ) -> str:
        audio_features = audio_features or {}
        imu_features = imu_features or {}
        state_features = state_features or {}
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        fortune = _pick_fortune()
        expo = expo_recommendation or self.create_expo_recommendation()
        motif = {
            "country": expo.get("country", "日本"),
            "feature": expo.get("feature", "丁寧な積み重ねが未来につながる気配"),
            "pavilion": expo.get("pavilion", "日本館"),
            "travel": expo.get("travel", "大阪"),
        }
        cuisine = expo.get("cuisine", "")
        restaurant = expo.get("restaurant", "")
        advice_line = expo.get("advice", random.choice(ADVICE))
        analysis_lines = _build_analysis_lines(
            audio_features=audio_features,
            imu_features=imu_features,
            state=state_features,
        )
        lines = [
            "{0}{1}{2}".format(
                TITLE_TOKEN_PREFIX, self.config.shrine_name, TITLE_TOKEN_SUFFIX
            ),
            "御神籤",
            "",
            TORII_TOKEN,
            "",
            "日時: {0}".format(now),
            "",
            "{0}【運勢】{1}{2}".format(
                FORTUNE_TOKEN_PREFIX,
                fortune,
                FORTUNE_TOKEN_SUFFIX,
            ),
            "",
            "いまの状態: {0}".format(str(state).upper()),
            "いのち輝く未来社会にむかって:",
            message,
            "",
            ALIGN_LEFT_TOKEN,
            "【EXPO 2025 モチーフ】",
            "国: {0}".format(motif["country"]),
            "気配: {0}".format(motif["feature"]),
            "おすすめパビリオン: {0}".format(motif["pavilion"]),
            "おすすめ旅先: {0}".format(motif["travel"]),
            "おすすめ料理: {0}".format(cuisine or "情報準備中"),
            "おすすめレストラン: {0}".format(restaurant or "情報準備中"),
            "今日の一言: {0}".format(advice_line),
            "",
            "【解析サマリー(セッション平均)】",
        ]
        lines.extend(analysis_lines)
        lines.extend(
            [
            ALIGN_CENTER_TOKEN,
            "",
            "{0}{1}{2}".format(
                QRCODE_TOKEN_PREFIX,
                self.config.qr_url,
                QRCODE_TOKEN_SUFFIX,
            ),
            "------------------------------",
            "",
            ]
        )
        return "\n".join(lines)

    def build_print_job(
        self,
        state: str,
        message: str,
        audio_features=None,
        imu_features=None,
        state_features=None,
        expo_recommendation=None,
    ):
        ticket = self.format_ticket(
            state,
            message,
            audio_features=audio_features,
            imu_features=imu_features,
            state_features=state_features,
            expo_recommendation=expo_recommendation,
        )
        return {
            "job_id": str(uuid4()),
            "job_type": "omikuji",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_device": self.config.source_device,
            "state": state,
            "message": message,
            "audio_features": audio_features or {},
            "imu_features": imu_features or {},
            "state_features": state_features or {},
            "expo_recommendation": expo_recommendation or {},
            "ticket_text": ticket,
            "format": "plain_text",
        }

    def create_expo_recommendation(self):
        motif = _pick_expo_motif()
        return {
            "country": motif.get("country"),
            "feature": motif.get("feature"),
            "pavilion": motif.get("pavilion"),
            "travel": motif.get("travel"),
            "cuisine": _pick_recommended_cuisine(),
            "restaurant": _pick_recommended_restaurant(),
            "advice": random.choice(ADVICE),
        }

    def _send_http_job(self, payload) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if self.config.auth_token:
            headers["Authorization"] = f"Bearer {self.config.auth_token}"

        http_request = request.Request(
            self.config.endpoint_url,
            data=body,
            headers=headers,
            method="POST",
        )

        try:
            with request.urlopen(http_request, timeout=self.config.timeout_sec) as response:
                if response.status >= 400:
                    raise RuntimeError(f"Print server returned status {response.status}")
        except error.URLError as exc:
            raise RuntimeError(
                f"Failed to reach Raspberry Pi print server at {self.config.endpoint_url}"
            ) from exc

    def _send_cups_job(self, payload) -> None:
        cmd = _build_cups_cmd(self.config.cups_printer, self.config.cups_orientation)
        if cmd is None:
            raise RuntimeError("Neither lp nor lpr command is available for CUPS printing")

        ticket_text = payload.get("ticket_text", "")
        mode = (self.config.cups_mode or "text").lower()
        file_path = None
        cmd_with_options = list(cmd)

        if mode == "image":
            file_path = _render_text_to_image_path(
                text=ticket_text,
                font_path=self.config.cups_font_path,
                font_size=self.config.cups_font_size,
                width_px=self.config.cups_width_px,
                height_px=self.config.cups_height_px,
                line_spacing=self.config.cups_line_spacing,
                column_spacing=self.config.cups_column_spacing,
                layout=self.config.cups_layout,
                text_align=self.config.cups_text_align,
            )
            if file_path is None:
                self._logger.warning(
                    "Pillow is unavailable or image rendering failed. Falling back to text mode."
                )
                mode = "text"
            else:
                img_width_px, img_height_px = _image_size_px(file_path)
                if img_width_px and img_height_px:
                    # Star TSP series are effectively ~203dpi (8 dots/mm)
                    width_mm = max(50, int(round(img_width_px / 8.0)))
                    height_mm = max(40, int(round(img_height_px / 8.0)))
                    self._logger.info(
                        "CUPS image media: Custom.%sx%smm (from %sx%spx)",
                        width_mm,
                        height_mm,
                        img_width_px,
                        img_height_px,
                    )
                    cmd_with_options.extend(
                        [
                            "-o",
                            "media=Custom.{0}x{1}mm".format(width_mm, height_mm),
                        ]
                    )
                cmd_with_options.extend(
                    [
                        "-o",
                        "position=center",
                        "-o",
                        "scaling=100",
                    ]
                )

        if mode == "text":
            tmp = tempfile.NamedTemporaryFile(prefix="omikuji_", suffix=".txt", delete=False)
            file_path = tmp.name
            tmp.write(ticket_text.encode("utf-8"))
            tmp.close()

        if not file_path:
            raise RuntimeError("Failed to prepare print file")

        try:
            proc = subprocess.run(
                cmd_with_options + [file_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
        finally:
            try:
                os.unlink(file_path)
            except OSError:
                pass

        if proc.returncode != 0:
            message = proc.stderr.strip() or proc.stdout.strip() or "CUPS print command failed"
            raise RuntimeError(message)

    def dispatch_print_job(self, payload):
        if self.config.transport == "stdout":
            print(payload["ticket_text"])
            return payload

        if self.config.transport == "http":
            self._send_http_job(payload)
            return payload

        if self.config.transport == "cups":
            self._send_cups_job(payload)
            return payload

        raise ValueError(f"Unsupported printer transport: {self.config.transport}")

    def print_omikuji(self, state: str, message: str):
        payload = self.build_print_job(state, message)
        return self.dispatch_print_job(payload)
