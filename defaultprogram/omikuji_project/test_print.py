import argparse
import os
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont
import qrcode


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


def build_print_cmd(printer: str, orientation: str) -> list[str] | None:
    orientation_opt = []
    if orientation == "portrait":
        orientation_opt = ["-o", "orientation-requested=3"]
    elif orientation == "landscape":
        orientation_opt = ["-o", "orientation-requested=4"]

    lp_cmd = shutil.which("lp")
    if lp_cmd:
        return [lp_cmd, "-d", printer] + orientation_opt
    lpr_cmd = shutil.which("lpr")
    if lpr_cmd:
        return [lpr_cmd, "-P", printer] + orientation_opt
    return None


def choose_font_path(font_path: str | None) -> str | None:
    if font_path and os.path.exists(font_path):
        return font_path
    for path in DEFAULT_JA_FONTS:
        if os.path.exists(path):
            return path
    return None


def wrap_text_to_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    wrapped: list[str] = []
    for raw_line in text.splitlines() or [""]:
        stripped = raw_line.strip()
        if (
            stripped == TORII_TOKEN
            or (stripped.startswith(TITLE_TOKEN_PREFIX) and stripped.endswith(TITLE_TOKEN_SUFFIX))
            or (stripped.startswith(FORTUNE_TOKEN_PREFIX) and stripped.endswith(FORTUNE_TOKEN_SUFFIX))
            or (stripped.startswith(QRCODE_TOKEN_PREFIX) and stripped.endswith(QRCODE_TOKEN_SUFFIX))
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
                line = "" if line else ""
                if line == "" and draw.textlength(ch, font=font) <= max_width:
                    line = ch
        wrapped.append(line)
    if text.endswith("\n"):
        wrapped.append("")
    return wrapped


def render_text_to_image(text: str, font_path: str | None, font_size: int, width_px: int, line_spacing: int) -> str:
    resolved_font = choose_font_path(font_path)
    if resolved_font:
        font = ImageFont.truetype(resolved_font, font_size)
    else:
        font = ImageFont.load_default()

    def load_title_font(title_text: str) -> ImageFont.FreeTypeFont:
        if not resolved_font:
            return font
        max_size = max(font_size + 18, int(font_size * 2.1))
        min_size = max(16, font_size)
        probe_draw = ImageDraw.Draw(Image.new("L", (width_px, 100), color=255))
        for size in range(max_size, min_size - 1, -1):
            candidate = ImageFont.truetype(resolved_font, size)
            if probe_draw.textlength(title_text, font=candidate) <= (width_px - 24):
                return candidate
        return ImageFont.truetype(resolved_font, min_size)

    def load_fortune_font(fortune_text: str) -> ImageFont.FreeTypeFont:
        if not resolved_font:
            return font
        max_size = max(font_size + 12, int(font_size * 1.7))
        min_size = max(18, font_size + 4)
        probe_draw = ImageDraw.Draw(Image.new("L", (width_px, 100), color=255))
        for size in range(max_size, min_size - 1, -1):
            candidate = ImageFont.truetype(resolved_font, size)
            if probe_draw.textlength(fortune_text, font=candidate) <= (width_px - 28):
                return candidate
        return ImageFont.truetype(resolved_font, min_size)

    probe = Image.new("L", (width_px, 100), color=255)
    draw = ImageDraw.Draw(probe)
    margin = 16
    max_width = width_px - (margin * 2)
    lines = wrap_text_to_width(draw, text, font, max_width)

    ascent, descent = font.getmetrics()
    line_height = ascent + descent + line_spacing
    torii_height = max(96, line_height * 4)
    qr_size = min(220, max(140, int(width_px * 0.34)))
    total_h = margin * 2
    for line in lines:
        stripped = line.strip()
        if stripped == TORII_TOKEN:
            total_h += torii_height
        elif stripped.startswith(TITLE_TOKEN_PREFIX) and stripped.endswith(TITLE_TOKEN_SUFFIX):
            title_text = stripped[len(TITLE_TOKEN_PREFIX):-len(TITLE_TOKEN_SUFFIX)]
            title_font = load_title_font(title_text)
            ascent_t, descent_t = title_font.getmetrics()
            total_h += ascent_t + descent_t + line_spacing + 4
        elif stripped.startswith(FORTUNE_TOKEN_PREFIX) and stripped.endswith(FORTUNE_TOKEN_SUFFIX):
            fortune_text = stripped[len(FORTUNE_TOKEN_PREFIX):-len(FORTUNE_TOKEN_SUFFIX)]
            fortune_font = load_fortune_font(fortune_text)
            ascent_f, descent_f = fortune_font.getmetrics()
            total_h += ascent_f + descent_f + line_spacing + 6
        elif stripped.startswith(QRCODE_TOKEN_PREFIX) and stripped.endswith(QRCODE_TOKEN_SUFFIX):
            total_h += qr_size + line_spacing + 2
        else:
            total_h += line_height
    height_px = max(120, total_h)
    image = Image.new("L", (width_px, height_px), color=255)
    draw = ImageDraw.Draw(image)

    def draw_torii(y: int) -> int:
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

    def draw_qrcode(y: int, url: str) -> int:
        qr = qrcode.QRCode(border=1, box_size=6, error_correction=qrcode.constants.ERROR_CORRECT_M)
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
            y = draw_torii(y)
        elif stripped.startswith(TITLE_TOKEN_PREFIX) and stripped.endswith(TITLE_TOKEN_SUFFIX):
            title_text = stripped[len(TITLE_TOKEN_PREFIX):-len(TITLE_TOKEN_SUFFIX)]
            title_font = load_title_font(title_text)
            tw = draw.textlength(title_text, font=title_font)
            tx = max(margin, int((width_px - tw) / 2))
            draw.text((tx, y), title_text, fill=0, font=title_font)
            ascent_t, descent_t = title_font.getmetrics()
            y += ascent_t + descent_t + line_spacing + 4
        elif stripped.startswith(FORTUNE_TOKEN_PREFIX) and stripped.endswith(FORTUNE_TOKEN_SUFFIX):
            fortune_text = stripped[len(FORTUNE_TOKEN_PREFIX):-len(FORTUNE_TOKEN_SUFFIX)]
            fortune_font = load_fortune_font(fortune_text)
            fw = draw.textlength(fortune_text, font=fortune_font)
            fx = max(margin, int((width_px - fw) / 2))
            draw.text((fx, y), fortune_text, fill=0, font=fortune_font)
            ascent_f, descent_f = fortune_font.getmetrics()
            y += ascent_f + descent_f + line_spacing + 6
        elif stripped.startswith(QRCODE_TOKEN_PREFIX) and stripped.endswith(QRCODE_TOKEN_SUFFIX):
            url = stripped[len(QRCODE_TOKEN_PREFIX):-len(QRCODE_TOKEN_SUFFIX)]
            y = draw_qrcode(y, url)
        else:
            draw.text((margin, y), line, fill=0, font=font)
            y += line_height

    tmp = tempfile.NamedTemporaryFile(prefix="star_print_", suffix=".png", delete=False)
    tmp_path = tmp.name
    tmp.close()
    image.save(tmp_path, format="PNG")
    return tmp_path


def render_vertical_text_to_image(
    text: str,
    font_path: str | None,
    font_size: int,
    width_px: int,
    height_px: int,
    line_spacing: int,
    column_spacing: int,
) -> str:
    resolved_font = choose_font_path(font_path)
    if resolved_font:
        font = ImageFont.truetype(resolved_font, font_size)
    else:
        font = ImageFont.load_default()

    ascent, descent = font.getmetrics()
    row_height = ascent + descent + line_spacing
    col_width = font_size + column_spacing
    margin = 16
    usable_rows = max(1, (height_px - margin * 2) // row_height)

    columns: list[str] = []
    lines = text.splitlines()
    for src_line in lines:
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

    tmp = tempfile.NamedTemporaryFile(prefix="star_print_", suffix=".png", delete=False)
    tmp_path = tmp.name
    tmp.close()
    image.save(tmp_path, format="PNG")
    return tmp_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--printer", default="star", help="CUPS printer queue name")
    parser.add_argument("--text", default="OMIKUJI TEST\n", help="Text to print")
    parser.add_argument("--mode", choices=["text", "image"], default="image", help="Print mode")
    parser.add_argument("--font-path", default=None, help="Path to .ttf/.ttc font file")
    parser.add_argument("--font-size", type=int, default=30, help="Font size for image mode")
    parser.add_argument("--width-px", type=int, default=576, help="Image width in pixels for image mode")
    parser.add_argument("--height-px", type=int, default=1400, help="Image height in pixels for vertical image mode")
    parser.add_argument("--line-spacing", type=int, default=4, help="Extra line spacing for image mode")
    parser.add_argument("--column-spacing", type=int, default=8, help="Extra spacing between vertical columns")
    parser.add_argument("--layout", choices=["horizontal", "vertical"], default="horizontal", help="Text layout for image mode")
    parser.add_argument("--orientation", choices=["auto", "portrait", "landscape"], default="portrait", help="Paper orientation")
    args = parser.parse_args()

    cmd = build_print_cmd(args.printer, args.orientation)
    if not cmd:
        print("ERROR: neither lp nor lpr command was found.", file=sys.stderr)
        return 1

    image_path = None
    try:
        if args.mode == "image":
            if args.layout == "vertical":
                image_path = render_vertical_text_to_image(
                    text=args.text,
                    font_path=args.font_path,
                    font_size=args.font_size,
                    width_px=args.width_px,
                    height_px=args.height_px,
                    line_spacing=args.line_spacing,
                    column_spacing=args.column_spacing,
                )
            else:
                image_path = render_text_to_image(
                    text=args.text,
                    font_path=args.font_path,
                    font_size=args.font_size,
                    width_px=args.width_px,
                    line_spacing=args.line_spacing,
                )
            proc = subprocess.run(
                cmd + [image_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
        else:
            proc = subprocess.run(
                cmd,
                input=args.text.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace").strip()
        print(f"ERROR: print command failed: {stderr}", file=sys.stderr)
        return exc.returncode or 1
    finally:
        if image_path and os.path.exists(image_path):
            os.remove(image_path)

    job_info = proc.stdout.decode("utf-8", errors="replace").strip()
    if job_info:
        print(job_info)
    print(f"Sent to CUPS queue: {args.printer}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
