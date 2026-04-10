from datetime import datetime, timezone
import json
import logging
import os
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

FORTUNE_WEIGHTS = [
    ("大吉", 8),
    ("中吉", 14),
    ("小吉", 18),
    ("吉", 20),
    ("末吉", 18),
    ("凶", 16),
    ("大凶", 6),
]

WISH = {
    "大吉": "願いごとは思いのほか早くかなうでしょう。",
    "中吉": "願いごとは努力を重ねればかないます。",
    "小吉": "願いごとは焦らず進めると良い結果に。",
    "吉": "願いごとは周囲の助けで形になります。",
    "末吉": "願いごとは時間をかけるほど実ります。",
    "凶": "願いごとは今は控え、準備を整えましょう。",
    "大凶": "願いごとは無理をせず時機を待ちましょう。",
}

LUCKY_ITEMS = [
    "白いハンカチ",
    "温かいお茶",
    "青いボールペン",
    "新しいメモ帳",
    "小さな観葉植物",
    "木のお守り",
    "柑橘系の香り",
]

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


def _pick_fortune():
    names = [name for name, _ in FORTUNE_WEIGHTS]
    weights = [weight for _, weight in FORTUNE_WEIGHTS]
    return random.choices(names, weights=weights, k=1)[0]


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


def _render_text_horizontal_image_path(text, font_path, font_size, width_px, line_spacing):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return None

    resolved_font = _choose_font_path(font_path)
    if resolved_font:
        font = ImageFont.truetype(resolved_font, font_size)
    else:
        font = ImageFont.load_default()

    probe = Image.new("L", (width_px, 100), color=255)
    probe_draw = ImageDraw.Draw(probe)
    margin = 16
    max_width = width_px - (margin * 2)
    lines = _wrap_text_to_width(probe_draw, text, font, max_width)

    def _load_title_font(title_text):
        if not resolved_font:
            return font
        max_size = max(font_size + 18, int(font_size * 2.1))
        min_size = max(16, font_size)
        for size in range(max_size, min_size - 1, -1):
            candidate = ImageFont.truetype(resolved_font, size)
            if probe_draw.textlength(title_text, font=candidate) <= (width_px - 24):
                return candidate
        return ImageFont.truetype(resolved_font, min_size)

    def _load_fortune_font(fortune_text):
        if not resolved_font:
            return font
        max_size = max(font_size + 12, int(font_size * 1.7))
        min_size = max(18, font_size + 4)
        for size in range(max_size, min_size - 1, -1):
            candidate = ImageFont.truetype(resolved_font, size)
            if probe_draw.textlength(fortune_text, font=candidate) <= (width_px - 28):
                return candidate
        return ImageFont.truetype(resolved_font, min_size)

    ascent, descent = font.getmetrics()
    line_height = ascent + descent + line_spacing
    torii_height = max(96, line_height * 4)
    qr_size = min(220, max(140, int(width_px * 0.34)))

    total_height = margin * 2
    for line in lines:
        stripped = line.strip()
        if stripped == TORII_TOKEN:
            total_height += torii_height
        elif stripped.startswith(TITLE_TOKEN_PREFIX) and stripped.endswith(TITLE_TOKEN_SUFFIX):
            title_text = stripped[len(TITLE_TOKEN_PREFIX) : -len(TITLE_TOKEN_SUFFIX)]
            title_font = _load_title_font(title_text)
            ascent_t, descent_t = title_font.getmetrics()
            total_height += ascent_t + descent_t + line_spacing + 4
        elif stripped.startswith(FORTUNE_TOKEN_PREFIX) and stripped.endswith(
            FORTUNE_TOKEN_SUFFIX
        ):
            fortune_text = stripped[len(FORTUNE_TOKEN_PREFIX) : -len(FORTUNE_TOKEN_SUFFIX)]
            fortune_font = _load_fortune_font(fortune_text)
            ascent_f, descent_f = fortune_font.getmetrics()
            total_height += ascent_f + descent_f + line_spacing + 6
        elif stripped.startswith(QRCODE_TOKEN_PREFIX) and stripped.endswith(
            QRCODE_TOKEN_SUFFIX
        ):
            total_height += qr_size + line_spacing + 2
        else:
            total_height += line_height
    height_px = max(240, total_height)

    image = Image.new("L", (width_px, height_px), color=255)
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
    for line in lines:
        stripped = line.strip()
        if stripped == TORII_TOKEN:
            y = _draw_torii(y)
        elif stripped.startswith(TITLE_TOKEN_PREFIX) and stripped.endswith(TITLE_TOKEN_SUFFIX):
            title_text = stripped[len(TITLE_TOKEN_PREFIX) : -len(TITLE_TOKEN_SUFFIX)]
            title_font = _load_title_font(title_text)
            tw = draw.textlength(title_text, font=title_font)
            tx = max(margin, int((width_px - tw) / 2))
            draw.text((tx, y), title_text, fill=0, font=title_font)
            ascent_t, descent_t = title_font.getmetrics()
            y += ascent_t + descent_t + line_spacing + 4
        elif stripped.startswith(FORTUNE_TOKEN_PREFIX) and stripped.endswith(
            FORTUNE_TOKEN_SUFFIX
        ):
            fortune_text = stripped[len(FORTUNE_TOKEN_PREFIX) : -len(FORTUNE_TOKEN_SUFFIX)]
            fortune_font = _load_fortune_font(fortune_text)
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
            draw.text((margin, y), line, fill=0, font=font)
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
    )


class Printer:
    """Sends print jobs to a Raspberry Pi print service or stdout."""

    def __init__(self, config: PrinterConfig) -> None:
        self.config = config
        self._logger = logging.getLogger(__name__)

    def format_ticket(self, state: str, message: str) -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        fortune = _pick_fortune()
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
            "状態: {0}".format(str(state).upper()),
            "啓示:",
            message,
            "",
            "願望: {0}".format(WISH.get(fortune, "焦らず進めば道が開けます。")),
            "ラッキーアイテム: {0}".format(random.choice(LUCKY_ITEMS)),
            "今日の一言: {0}".format(random.choice(ADVICE)),
            "",
            "{0}{1}{2}".format(
                QRCODE_TOKEN_PREFIX,
                self.config.qr_url,
                QRCODE_TOKEN_SUFFIX,
            ),
            "------------------------------",
            "",
        ]
        return "\n".join(lines)

    def build_print_job(self, state: str, message: str):
        ticket = self.format_ticket(state, message)
        return {
            "job_id": str(uuid4()),
            "job_type": "omikuji",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_device": self.config.source_device,
            "state": state,
            "message": message,
            "ticket_text": ticket,
            "format": "plain_text",
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
            )
            if file_path is None:
                self._logger.warning(
                    "Pillow is unavailable or image rendering failed. Falling back to text mode."
                )
                mode = "text"

        if mode == "text":
            tmp = tempfile.NamedTemporaryFile(prefix="omikuji_", suffix=".txt", delete=False)
            file_path = tmp.name
            tmp.write(ticket_text.encode("utf-8"))
            tmp.close()

        if not file_path:
            raise RuntimeError("Failed to prepare print file")

        try:
            proc = subprocess.run(
                cmd + [file_path],
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
