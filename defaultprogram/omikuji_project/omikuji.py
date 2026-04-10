import argparse
import json
import os
import random
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib import error, request


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

BUSINESS = {
    "大吉": "商いは新しい縁が広がり、大きく発展します。",
    "中吉": "商いは堅実に進めるほど利益が出ます。",
    "小吉": "商いは小さな改善が成果につながります。",
    "吉": "商いは信用第一で進めると吉。",
    "末吉": "商いは守りを固めると後に伸びます。",
    "凶": "商いは大きな投資を避け、見直しを優先。",
    "大凶": "商いは無理な拡大を避け、基盤を整えること。",
}

STUDY = {
    "大吉": "学業は集中力が高まり、大きく前進します。",
    "中吉": "学業は計画通りに進めれば成果十分。",
    "小吉": "学業は基礎の見直しが運を開きます。",
    "吉": "学業は毎日の積み重ねが力になります。",
    "末吉": "学業は復習を丁寧にすると安定します。",
    "凶": "学業は焦り禁物。目標を小さく分けて。",
    "大凶": "学業は一度立て直し、生活リズムを整えましょう。",
}

LOVE = {
    "大吉": "恋愛は素直な気持ちが実を結びます。",
    "中吉": "恋愛は思いやりを示せば順調です。",
    "小吉": "恋愛は言葉より行動で伝えると吉。",
    "吉": "恋愛は距離感を大切にすれば安定します。",
    "末吉": "恋愛は急がず、信頼を育てると良い。",
    "凶": "恋愛は感情的にならず、落ち着いて対話を。",
    "大凶": "恋愛は無理に進めず、自分を整える時。",
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

SHRINE_NAME = "ぬるみゃく神社"
TORII_MARKER = "[[TORII]]"
TITLE_MARKER_PREFIX = "[[TITLE:"
TITLE_MARKER_SUFFIX = "]]"
FORTUNE_MARKER_PREFIX = "[[FORTUNE:"
FORTUNE_MARKER_SUFFIX = "]]"
QRCODE_MARKER_PREFIX = "[[QRCODE:"
QRCODE_MARKER_SUFFIX = "]]"
DEFAULT_PRINT_FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
DEFAULT_QR_URL = "https://www.yahoo.co.jp/"
MYTH_HISTORY_FILE = Path(__file__).resolve().parent / ".myth_history.json"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"

LOCAL_MYTHS = [
    {
        "source": "古事記",
        "title": "天岩戸",
        "episode": "天照大神が岩戸に隠れ世界が闇に包まれたとき、神々が知恵を集めて光を取り戻した。",
        "lesson": "塞いだ心は、一人で抱えず周囲の力を借りると開ける。",
    },
    {
        "source": "日本書紀",
        "title": "国譲り",
        "episode": "大国主神が国を譲り、新しい秩序の下で国づくりが進んだ。",
        "lesson": "役割を渡す勇気が、次の発展を生む。",
    },
    {
        "source": "古事記",
        "title": "因幡の白兎",
        "episode": "傷ついた兎は誤った助言で苦しむが、正しい知恵で癒やされた。",
        "lesson": "耳ざわりよりも本当に役立つ言葉を選ぶ。",
    },
    {
        "source": "日本書紀",
        "title": "ヤマトタケルの東征",
        "episode": "厳しい道のりでも策と覚悟で困難を越えた。",
        "lesson": "勢いだけでなく準備が旅を成功へ導く。",
    },
    {
        "source": "古事記",
        "title": "海幸彦・山幸彦",
        "episode": "兄弟の行き違いは、時間と誠意によって解かれていく。",
        "lesson": "失った信頼は丁寧な行動で取り戻せる。",
    },
]


def pick_fortune() -> str:
    names = [name for name, _ in FORTUNE_WEIGHTS]
    weights = [weight for _, weight in FORTUNE_WEIGHTS]
    return random.choices(names, weights=weights, k=1)[0]


def load_myth_history() -> list[str]:
    if not MYTH_HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(MYTH_HISTORY_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [str(x) for x in data]
    except Exception:
        return []
    return []


def save_myth_history(history: list[str]) -> None:
    MYTH_HISTORY_FILE.write_text(json.dumps(history[-12:], ensure_ascii=False, indent=2), encoding="utf-8")


def choose_local_myth(seed: int | None = None) -> dict[str, str]:
    if seed is not None:
        random.seed(seed)
    history = load_myth_history()
    candidates = [m for m in LOCAL_MYTHS if m["title"] not in history[-4:]]
    pool = candidates if candidates else LOCAL_MYTHS
    myth = random.choice(pool)
    history.append(myth["title"])
    save_myth_history(history)
    return myth


def call_openai_myth(model: str) -> dict[str, str]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    history = load_myth_history()
    recent = ", ".join(history[-5:]) if history else "なし"
    prompt = (
        "古事記または日本書紀をモチーフにした短いエピソードを1件生成してください。"
        "直近使用済みタイトルは避けること。"
        f"直近使用済み: {recent}\n"
        "必ずJSONのみを返す。キーは source,title,episode,lesson。"
        "sourceは『古事記』または『日本書紀』。"
        "episodeは120文字以内、lessonは60文字以内。"
    )

    payload = {
        "model": model,
        "input": prompt,
        "temperature": 0.9,
    }
    req = request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
    except error.URLError as exc:
        raise RuntimeError(f"OpenAI request failed: {exc}") from exc

    parsed = json.loads(body)
    output_text = parsed.get("output_text", "")
    if not output_text:
        raise RuntimeError("OpenAI response missing output_text")

    start = output_text.find("{")
    end = output_text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise RuntimeError("OpenAI response is not JSON")
    myth = json.loads(output_text[start : end + 1])
    for key in ("source", "title", "episode", "lesson"):
        if key not in myth:
            raise RuntimeError(f"OpenAI JSON missing key: {key}")

    history.append(str(myth["title"]))
    save_myth_history(history)
    return {k: str(myth[k]) for k in ("source", "title", "episode", "lesson")}


def get_myth(mode: str, model: str, seed: int | None = None) -> tuple[dict[str, str], str]:
    if mode == "local":
        return choose_local_myth(seed=seed), "local"
    if mode == "llm":
        return call_openai_myth(model=model), "llm"
    try:
        return call_openai_myth(model=model), "llm"
    except Exception:
        return choose_local_myth(seed=seed), "local"


def build_omikuji_text(seed: int | None = None, myth: dict[str, str] | None = None, qr_url: str = DEFAULT_QR_URL) -> str:
    if seed is not None:
        random.seed(seed)

    fortune = pick_fortune()
    myth_data = myth or choose_local_myth(seed=seed)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"{TITLE_MARKER_PREFIX}{SHRINE_NAME}{TITLE_MARKER_SUFFIX}",
        "御神籤",
        "",
        TORII_MARKER,
        "",
        f"日時: {now}",
        "",
        f"{FORTUNE_MARKER_PREFIX}【運勢】{fortune}{FORTUNE_MARKER_SUFFIX}",
        "",
        f"願望: {WISH[fortune]}",
        f"商売: {BUSINESS[fortune]}",
        f"学業: {STUDY[fortune]}",
        f"恋愛: {LOVE[fortune]}",
        "",
        f"神話: {myth_data['source']}「{myth_data['title']}」",
        f"物語: {myth_data['episode']}",
        f"示唆: {myth_data['lesson']}",
        "",
        f"ラッキーアイテム: {random.choice(LUCKY_ITEMS)}",
        f"今日の一言: {random.choice(ADVICE)}",
        "",
        f"{QRCODE_MARKER_PREFIX}{qr_url}{QRCODE_MARKER_SUFFIX}",
        "------------------------------",
        "",
    ]
    return "\n".join(lines)


def preview_text(text: str) -> str:
    out = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(TITLE_MARKER_PREFIX) and stripped.endswith(TITLE_MARKER_SUFFIX):
            out.append(stripped[len(TITLE_MARKER_PREFIX):-len(TITLE_MARKER_SUFFIX)])
        elif stripped.startswith(FORTUNE_MARKER_PREFIX) and stripped.endswith(FORTUNE_MARKER_SUFFIX):
            out.append(stripped[len(FORTUNE_MARKER_PREFIX):-len(FORTUNE_MARKER_SUFFIX)])
        elif stripped.startswith(QRCODE_MARKER_PREFIX) and stripped.endswith(QRCODE_MARKER_SUFFIX):
            out.append("QR: " + stripped[len(QRCODE_MARKER_PREFIX):-len(QRCODE_MARKER_SUFFIX)])
        else:
            out.append(line)
    return "\n".join(out)


def print_with_test_print(text: str, printer: str) -> int:
    test_print = Path(__file__).resolve().parent / "test_print.py"
    cmd = [
        sys.executable,
        str(test_print),
        "--printer",
        printer,
        "--mode",
        "image",
        "--layout",
        "horizontal",
        "--orientation",
        "portrait",
        "--font-path",
        DEFAULT_PRINT_FONT,
        "--text",
        text,
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.stdout.strip():
        print(proc.stdout.strip())
    if proc.returncode != 0:
        print(proc.stderr.strip() or "print failed", file=sys.stderr)
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="一般的なおみくじを生成して表示/印刷します。")
    parser.add_argument("--seed", type=int, default=None, help="固定値を指定すると同じ結果を再現")
    parser.add_argument("--print", action="store_true", help="生成後にそのまま印刷する")
    parser.add_argument("--printer", default="star", help="印刷キュー名")
    parser.add_argument("--myth-mode", choices=["auto", "llm", "local"], default="auto", help="神話エピソード取得方法")
    parser.add_argument("--openai-model", default=DEFAULT_OPENAI_MODEL, help="OpenAI model name")
    parser.add_argument("--qr-url", default=DEFAULT_QR_URL, help="QRコードに埋め込むURL")
    args = parser.parse_args()

    myth, used_mode = get_myth(mode=args.myth_mode, model=args.openai_model, seed=args.seed)
    text = build_omikuji_text(seed=args.seed, myth=myth, qr_url=args.qr_url)
    print(preview_text(text))
    print(f"(myth source: {used_mode})")

    if args.print:
        return print_with_test_print(text, args.printer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
