#!/usr/bin/env python3
import argparse
import csv
import io
import html
import json
import re
from datetime import datetime, timezone
from urllib import request
from urllib.parse import urlparse


DEFAULT_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "12a0ryfhimMX_F7pYD09WdV4vlelZmvSBkpb0pAuX_ac/edit?gid=0#gid=0"
)
DEFAULT_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "12a0ryfhimMX_F7pYD09WdV4vlelZmvSBkpb0pAuX_ac/export?format=csv&gid=0"
)
DEFAULT_NOTE_URL = "https://note.com/___basho/n/n27450ab634f8"
DEFAULT_OUTPUT = "docs/expo_catalog.json"


TRAVEL_MAP = {
    "アイルランド": "ダブリン",
    "アゼルバイジャン": "バクー",
    "アメリカ": "ニューヨーク",
    "イタリア": "ローマ",
    "インドネシア": "ジャカルタ",
    "ウズベキスタン": "サマルカンド",
    "オーストラリア": "シドニー",
    "オーストリア": "ウィーン",
    "オマーン": "マスカット",
    "オランダ": "アムステルダム",
    "カタール": "ドーハ",
    "カナダ": "バンクーバー",
    "クウェート": "クウェートシティ",
    "コロンビア": "ボゴタ",
    "サウジアラビア": "リヤド",
    "スイス": "チューリッヒ",
    "スペイン": "バルセロナ",
    "チェコ": "プラハ",
    "中国": "上海",
    "ドイツ": "ベルリン",
    "トルクメニスタン": "アシガバート",
    "トルコ": "イスタンブール",
    "ルクセンブルク": "ルクセンブルク市",
    "アラブ首長国連邦": "ドバイ",
    "アンゴラ": "ルアンダ",
    "インド": "デリー",
    "英国": "ロンドン",
    "エジプト": "カイロ",
    "EU": "ブリュッセル",
    "カンボジア": "プノンペン",
    "シンガポール": "シンガポール",
    "セネガル": "ダカール",
    "セルビア": "ベオグラード",
    "タイ": "バンコク",
    "大韓民国": "ソウル",
    "チュニジア": "チュニス",
    "チリ": "サンティアゴ",
    "ネパール": "カトマンズ",
    "バーレーン": "マナーマ",
    "バルト": "リガ",
    "ハンガリー": "ブダペスト",
    "バングラデシュ": "ダッカ",
    "フィリピン": "マニラ",
    "ブラジル": "サンパウロ",
    "フランス": "パリ",
    "ブルガリア": "ソフィア",
    "ベトナム": "ホーチミン",
    "ペルー": "リマ",
    "ベルギー": "ブリュッセル",
    "ポーランド": "ワルシャワ",
    "ポルトガル": "リスボン",
    "マルタ": "バレッタ",
    "マレーシア": "クアラルンプール",
    "モザンビーク": "マプト",
    "モナコ": "モナコ",
    "ヨルダン": "アンマン",
    "ルーマニア": "ブカレスト",
    "アルジェリア": "アルジェ",
}

ZONE_FEATURE = {
    "エ": "先端技術と実装力が噛み合い、判断に推進力が出る気配",
    "コ": "交流とつながりが広がり、共創のアイデアが生まれる気配",
    "セ": "落ち着きと持続性が高まり、丁寧な選択が活きる気配",
    "東": "集中と立ち上がりが強まり、最初の一歩が軽くなる気配",
    "西": "開放感と行動力が増し、流れに乗って前進できる気配",
    "フ": "未来志向が高まり、次の展開を描きやすくなる気配",
}


def _clean_name(name):
    value = (name or "").strip()
    value = re.sub(r"\s*\(.*?\)", "", value)
    return value.strip()


def _country_from_pavilion(pavilion):
    match = re.match(r"^(.*?)館$", pavilion or "")
    if match:
        return match.group(1).strip()
    return pavilion or ""


def _infer_cuisine_label(shop_name):
    name = (shop_name or "").strip()
    lower = name.lower()
    rules = [
        (("カレー",), "カレー"),
        (("ラーメン", "ramen"), "ラーメン"),
        (("うどん",), "うどん"),
        (("寿司", "すし", "スシ"), "寿司"),
        (("串かつ",), "串かつ"),
        (("たこ",), "たこ焼き"),
        (("パン", "bakery"), "パン"),
        (("ケバブ", "kebab"), "ケバブ"),
        (("pizza", "ピザ"), "ピザ"),
        (("韓国", "ソウル", "bibim", "景福宮"), "韓国料理"),
        (("エスニック",), "エスニック料理"),
        (("ハラル",), "ハラル料理"),
        (("スイーツ", "sweets", "ケーキ"), "スイーツ"),
        (("ドイツ", "oktoberfest"), "ドイツ料理"),
        (("トルコ", "istanbul"), "トルコ料理"),
    ]
    for keys, cuisine in rules:
        for key in keys:
            if key in name or key in lower:
                return cuisine + "（" + name + "）"
    return name


def _download_csv(url):
    with request.urlopen(url, timeout=30) as response:
        return response.read().decode("utf-8", "ignore")


def _download_text(url):
    with request.urlopen(url, timeout=30) as response:
        return response.read().decode("utf-8", "ignore")


def _extract_note_key(note_url):
    path = urlparse(note_url).path
    match = re.search(r"/n/([a-z0-9]+)", path)
    if not match:
        return None
    return match.group(1)


def _download_note_body_html(note_url):
    note_key = _extract_note_key(note_url)
    if not note_key:
        return ""
    api_url = "https://note.com/api/v3/notes/{0}".format(note_key)
    try:
        raw = _download_text(api_url)
        payload = json.loads(raw)
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        body = data.get("body", "")
        if isinstance(body, str):
            return body
    except Exception:
        return ""
    return ""


def _strip_html(value):
    text = value
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</(p|li|h[1-6])>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text)


def _normalize_candidate(text):
    line = (text or "").replace("\u3000", " ").strip()
    line = re.sub(r"\s+", " ", line)
    line = re.sub(r"^[\-\*\u2022・]+\s*", "", line)
    line = re.sub(r"^\(\d+\)\s*", "", line)
    line = line.rstrip(":：")

    # Keep the Japanese side when line has bilingual notation.
    if " / " in line:
        parts = [part.strip() for part in line.split(" / ") if part.strip()]
        if parts:
            jp_parts = [part for part in parts if re.search(r"[ぁ-んァ-ヶ一-龥]", part)]
            line = jp_parts[0] if jp_parts else parts[0]

    # Remove trailing price expression and quantities.
    line = re.sub(r"\s*¥\s*[0-9,]{2,6}.*$", "", line)
    line = re.sub(r"\s+\d+\s*(pc|pcs|個)\b", "", line, flags=re.IGNORECASE)
    line = re.sub(r"\s*\(\s*[0-9]+\s*ml[^)]*\)\s*", "", line, flags=re.IGNORECASE)
    line = line.rstrip(":：")
    line = line.strip("・ ")
    line = re.sub(r"\s+", " ", line).strip()
    return line


def _extract_cuisines_from_note(note_html):
    text = _strip_html(note_html)
    candidates = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if "¥" not in line:
            continue
        normalized = _normalize_candidate(line)
        if len(normalized) < 2 or len(normalized) > 90:
            continue
        if re.fullmatch(r"[0-9,\.]+\s*(ml|l|L)?", normalized):
            continue
        candidates.append(normalized)

    exclude_keywords = [
        "ビール",
        "ワイン",
        "スパークリング",
        "ソフトドリンク",
        "コカコーラ",
        "ジュース",
        "トニック",
        "ジンジャーエール",
        "ミネラルウォーター",
        "カクテル",
        "ノンアルコール",
        "コーヒー",
        "紅茶",
        "ティー",
        "アイスティー",
        "エスプレッソ",
        "ラテ",
        "カプチーノ",
        "チャイ",
        "ドリンク",
        "ml",
        "l ",
        "Hot",
        "Ice",
        "ジュース",
        "ウォーター",
        "ハイボール",
        "サワー",
        "コーラ",
        "ジントニック",
        "アイスコーヒー",
        "カフェオレ",
        "アメリカーノ",
        "ピッコロ",
        "フラットホワイト",
        "ロングブラック",
        "リストレット",
        "モカ",
        "炭酸水",
        "スパークリング",
        "ロゼ",
        "ピノノワール",
        "シャルドネ",
        "メルロー",
        "ソーヴィニヨン",
        "ブランデー",
        "レモネード",
        "ブラッドオレンジ",
        "グレープフルーツ",
        "ゆず",
        "カシス",
        "エルダーベリー",
        "イェーガーマイスター",
        "ベビチーノ",
        "テータリック",
    ]
    deduped = []
    seen = set()
    for line in candidates:
        lowered = line.lower()
        if any(keyword.lower() in lowered for keyword in exclude_keywords):
            continue
        if re.search(r"（\s*(赤|白|ロゼ)\s*）$", line):
            continue
        if line.endswith("各"):
            continue
        if line not in seen:
            seen.add(line)
            deduped.append(line)
    return deduped[:180]


def build_catalog(csv_text, sheet_url, csv_url, note_url):
    rows = list(csv.reader(io.StringIO(csv_text)))
    motifs = []
    restaurants = []
    seen = set()
    seen_restaurant = set()
    for row in rows:
        if len(row) < 5:
            continue
        category = row[2].strip()
        zone = row[3].strip()
        pavilion = _clean_name(row[4])
        if category == "食":
            if pavilion:
                if pavilion not in seen_restaurant:
                    seen_restaurant.add(pavilion)
                    restaurants.append(pavilion)
            continue
        if category != "外":
            continue
        if not pavilion or "館" not in pavilion:
            continue
        if pavilion in seen:
            continue
        seen.add(pavilion)

        country = _country_from_pavilion(pavilion)
        feature = ZONE_FEATURE.get(zone, "感性と行動のバランスが整い、次の選択が明確になる気配")
        travel = TRAVEL_MAP.get(country, country + "の主要都市")
        motifs.append(
            {
                "country": country,
                "feature": feature,
                "pavilion": pavilion,
                "travel": travel,
            }
        )

    note_html = _download_note_body_html(note_url)
    if not note_html:
        note_html = _download_text(note_url)
    cuisines = _extract_cuisines_from_note(note_html)
    if not cuisines:
        cuisines = [_infer_cuisine_label(name) for name in restaurants]

    return {
        "source": {
            "sheet_url": sheet_url,
            "csv_export_url": csv_url,
            "note_url": note_url,
            "note_api_url": (
                "https://note.com/api/v3/notes/{0}".format(_extract_note_key(note_url))
                if _extract_note_key(note_url)
                else ""
            ),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "filter": "motifs: cat=外 and pavilion contains 館 / restaurants: cat=食 / cuisines: note menu lines",
        },
        "motifs": motifs,
        "cuisines": cuisines,
        "restaurants": restaurants,
    }


def main():
    parser = argparse.ArgumentParser(description="Build expo_catalog.json from Google Sheets CSV")
    parser.add_argument("--sheet-url", default=DEFAULT_SHEET_URL)
    parser.add_argument("--csv-url", default=DEFAULT_CSV_URL)
    parser.add_argument("--note-url", default=DEFAULT_NOTE_URL)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    csv_text = _download_csv(args.csv_url)
    payload = build_catalog(csv_text, args.sheet_url, args.csv_url, args.note_url)
    with open(args.output, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)
    print(
        "Wrote %s motifs=%d cuisines=%d restaurants=%d"
        % (
            args.output,
            len(payload.get("motifs", [])),
            len(payload.get("cuisines", [])),
            len(payload.get("restaurants", [])),
        )
    )


if __name__ == "__main__":
    main()
