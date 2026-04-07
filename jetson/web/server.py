from __future__ import annotations

from pathlib import Path


def load_index() -> str:
    static_path = Path(__file__).with_name("static") / "index.html"
    return static_path.read_text(encoding="utf-8")
