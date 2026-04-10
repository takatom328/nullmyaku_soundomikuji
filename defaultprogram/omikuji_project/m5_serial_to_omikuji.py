#!/usr/bin/env python3
# m5_serial_to_omikuji.py
#
# M5Stack Core2 -> (USB Serial, 1-line JSON) -> Raspberry Pi4
# -> build omikuji text (existing omikuji.py) -> print via CUPS (existing test_print.py)
# + sqlite persistence for "continuation chapters" by sig
# + debounce/anti-spam + auto serial reconnect + logging + print retry

import argparse
import hashlib
import json
import os
import sqlite3
import time
from urllib.parse import quote

import serial  # sudo apt install python3-serial

import omikuji  # same directory


# ---------- Persistence (SQLite) ----------
def init_db(db_path: str) -> None:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with sqlite3.connect(db_path) as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            sig TEXT PRIMARY KEY,
            visit_count INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """)
        con.commit()


def touch_profile(db_path: str, sig: str) -> int:
    """
    Increment visit_count for sig and return new count.
    NOTE: 呼び出し側で「ブロック判定」してから touch すること。
    """
    now = int(time.time())
    with sqlite3.connect(db_path) as con:
        cur = con.cursor()
        cur.execute("SELECT visit_count FROM profiles WHERE sig=?", (sig,))
        row = cur.fetchone()
        if row is None:
            cur.execute(
                "INSERT INTO profiles(sig, visit_count, created_at, updated_at) VALUES(?,?,?,?)",
                (sig, 1, now, now)
            )
            con.commit()
            return 1
        else:
            cnt = int(row[0]) + 1
            cur.execute(
                "UPDATE profiles SET visit_count=?, updated_at=? WHERE sig=?",
                (cnt, now, sig)
            )
            con.commit()
            return cnt


def stable_seed_from_sig(sig: str) -> int:
    h = hashlib.sha256(sig.encode("utf-8")).digest()
    return int.from_bytes(h[:4], "big")


# ---------- Logging ----------
def log_event(log_path: str, event: dict) -> None:
    """
    JSON Lines で追記。落ちても解析しやすい。
    """
    if not log_path:
        return
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    event = dict(event)
    event["ts"] = int(time.time())
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


# ---------- Text building ----------
def chapter_from_count(count: int) -> str:
    if count <= 1:
        return "CHAPTER 1: 序章"
    elif count == 2:
        return "CHAPTER 2: 巡礼"
    elif count == 3:
        return "CHAPTER 3: ひらめき"
    else:
        return f"CHAPTER {count}: 続編"


def build_expo_insert_lines(payload: dict, visit_count: int) -> list[str]:
    tags = payload.get("tags", [])
    imu = payload.get("imu", {}) or {}
    sig = payload.get("sig", "UNKNOWN")

    tag_set = set(tags)
    vibe = []
    if "burst" in tag_set or "active" in tag_set:
        vibe.append("勢いと好奇心が前に出る気配")
    if "gentle" in tag_set:
        vibe.append("丁寧に手触りを確かめる気配")
    if "steady" in tag_set:
        vibe.append("リズムよく積み上げる気配")
    if "free" in tag_set:
        vibe.append("寄り道で発見する気配")
    if "smooth" in tag_set:
        vibe.append("なめらかに整える気配")
    if "snappy" in tag_set:
        vibe.append("切り替えが速い気配")

    vibe_text = " / ".join(vibe) if vibe else "今日は素直に引けている気配"

    ch = chapter_from_count(visit_count)
    if visit_count <= 1:
        hint1 = "未来の展示は“仕組み”を見る"
        hint2 = "多様性は“背景”を想像する"
    elif visit_count == 2:
        hint1 = "次は“反対側”の視点で歩く"
        hint2 = "食と技術をセットで味わう"
    else:
        hint1 = "今日は“いのち”の流れを追う"
        hint2 = "一つだけ深掘りして帰る"

    a_pk = imu.get("a_pk", None)
    rhythm = imu.get("rhythm", None)
    metric = []
    if isinstance(a_pk, (int, float)):
        metric.append(f"勢い指数:{a_pk:.2f}")
    if isinstance(rhythm, (int, float)):
        metric.append(f"リズム指数:{rhythm:.2f}")
    metric_text = " / ".join(metric) if metric else ""

    lines = [
        "",
        f"【{ch}】",
        "【EXPOのしるし】",
        f"サイン: {vibe_text}",
        hint1,
        hint2,
    ]
    if metric_text:
        lines.append(metric_text)
    lines.append(f"引き方ID: {sig}")
    lines.append(f"Visit: {visit_count}")

    return lines


def insert_lines_before_qr(original_text: str, insert_lines: list[str]) -> str:
    out = []
    inserted = False
    for line in original_text.splitlines():
        stripped = line.strip()
        if (not inserted) and stripped.startswith(omikuji.QRCODE_MARKER_PREFIX) and stripped.endswith(omikuji.QRCODE_MARKER_SUFFIX):
            out.extend(insert_lines)
            inserted = True
        out.append(line)
    if not inserted:
        out.extend(insert_lines)
    return "\n".join(out) + ("\n" if not original_text.endswith("\n") else "")


# ---------- Serial loop with reconnect ----------
def open_serial(port: str, baud: int) -> serial.Serial:
    ser = serial.Serial(port, baud, timeout=1)
    time.sleep(0.4)
    try:
        ser.reset_input_buffer()
    except Exception:
        pass
    return ser


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/ttyACM0")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--printer", default="star")
    ap.add_argument("--myth-mode", choices=["auto", "llm", "local"], default="auto")
    ap.add_argument("--openai-model", default=omikuji.DEFAULT_OPENAI_MODEL)
    ap.add_argument("--qr-base", default="https://example.com/omikuji?sig=",
                    help="QRに埋めるURLのベース。末尾にsigを付ける")
    ap.add_argument("--db", default=os.path.expanduser("~/omikuji_project/state/omikuji.sqlite3"),
                    help="継続ID(引き方ID)の保存先SQLite")
    ap.add_argument("--log", default=os.path.expanduser("~/omikuji_project/state/events.jsonl"),
                    help="イベントログ(JSONL)の保存先。空ならログ無し")
    ap.add_argument("--block-sec", type=int, default=10,
                    help="同じsigの連続印刷ブロック秒数（章が進みすぎるのを防ぐ）")
    ap.add_argument("--print-retry", type=int, default=1,
                    help="印刷失敗時のリトライ回数（0/1推奨）")
    ap.add_argument("--reconnect-sec", type=int, default=1,
                    help="シリアル再接続の待ち秒数")
    args = ap.parse_args()

    init_db(args.db)

    # 同一sigの短時間連続をブロック
    last_print_ts_by_sig: dict[str, float] = {}

    print(f"Serial: {args.port} @ {args.baud}")
    print(f"Printer: {args.printer}")
    print(f"DB: {args.db}")
    print(f"LOG: {args.log}")
    print(f"Block: {args.block_sec}s, Retry: {args.print_retry}")

    ser = None
    while True:
        # 接続確立
        if ser is None:
            try:
                ser = open_serial(args.port, args.baud)
                print("[SERIAL] connected")
                log_event(args.log, {"event": "serial_connected", "port": args.port})
            except Exception as e:
                print(f"[SERIAL] connect failed: {e}")
                log_event(args.log, {"event": "serial_connect_failed", "error": str(e)})
                time.sleep(args.reconnect_sec)
                continue

        # 読み取り
        try:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
        except Exception as e:
            print(f"[SERIAL] read error: {e} -> reconnect")
            log_event(args.log, {"event": "serial_read_error", "error": str(e)})
            try:
                ser.close()
            except Exception:
                pass
            ser = None
            time.sleep(args.reconnect_sec)
            continue

        if not line:
            continue

        # JSON decode
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            print(f"[WARN] non-json: {line[:120]}")
            log_event(args.log, {"event": "rx_non_json", "line": line[:200]})
            continue

        if payload.get("type") != "omikuji":
            log_event(args.log, {"event": "rx_ignore", "type": payload.get("type")})
            continue

        sig = str(payload.get("sig", "UNKNOWN"))
        now = time.time()

        # ブロック判定（印刷前に）
        last_ts = last_print_ts_by_sig.get(sig, 0.0)
        if args.block_sec > 0 and (now - last_ts) < args.block_sec:
            remain = args.block_sec - (now - last_ts)
            print(f"[BLOCK] sig={sig} remain={remain:.1f}s")
            log_event(args.log, {"event": "blocked", "sig": sig, "remain_sec": round(remain, 2)})
            continue

        # ここで visit_count を進める（＝章を進める）
        visit_count = touch_profile(args.db, sig)
        last_print_ts_by_sig[sig] = now

        # seedはsig固定（同じ引き方→同じベース）
        seed = stable_seed_from_sig(sig)

        # 神話（ローカル or LLM）は既存の仕組み
        myth, used_mode = omikuji.get_myth(mode=args.myth_mode, model=args.openai_model, seed=seed)

        # QRにsig（将来のWeb表示や続編のキー）
        qr_url = args.qr_base + quote(sig)

        base_text = omikuji.build_omikuji_text(seed=seed, myth=myth, qr_url=qr_url)
        expo_lines = build_expo_insert_lines(payload, visit_count)
        final_text = insert_lines_before_qr(base_text, expo_lines)

        print(f"[RX] sig={sig} visit={visit_count} tags={payload.get('tags')} (myth={used_mode})")
        log_event(args.log, {"event": "rx", "sig": sig, "visit": visit_count, "tags": payload.get("tags"), "myth": used_mode})

        # 印刷（失敗時は1回だけリトライ）
        ok = False
        for attempt in range(args.print_retry + 1):
            rc = omikuji.print_with_test_print(final_text, args.printer)
            if rc == 0:
                ok = True
                break
            print(f"[ERR] print failed rc={rc} attempt={attempt+1}/{args.print_retry+1}")
            log_event(args.log, {"event": "print_failed", "sig": sig, "visit": visit_count, "rc": rc, "attempt": attempt + 1})
            time.sleep(0.4)

        if ok:
            print("[OK] printed")
            log_event(args.log, {"event": "printed", "sig": sig, "visit": visit_count})


if __name__ == "__main__":
    main()