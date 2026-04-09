import json
from datetime import datetime
from pathlib import Path

from ..utils.config import SessionConfig


class SessionArchive:
    def __init__(self, config: SessionConfig, logger) -> None:
        self.config = config
        self.logger = logger
        self._last_saved_path = None
        self._last_error = None
        self._saved_count = 0
        self._base_dir = self._resolve_base_dir(config.archive_dir)
        if self.config.archive_enabled:
            self._ensure_directory()

    def _resolve_base_dir(self, raw_path):
        path = Path((raw_path or "sessions")).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        return path

    def _ensure_directory(self):
        try:
            self._base_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._last_error = "Failed to create session archive dir: {0}".format(exc)
            self.logger.warning(self._last_error)

    def status(self):
        return {
            "enabled": self.config.archive_enabled,
            "dir": str(self._base_dir),
            "saved_count": self._saved_count,
            "last_saved_path": self._last_saved_path,
            "last_error": self._last_error,
        }

    def save(self, session_payload):
        if not self.config.archive_enabled:
            return None

        self._ensure_directory()
        if self._last_error and not self._base_dir.exists():
            return None

        meta = session_payload.get("meta", {})
        session_id = str(meta.get("session_id", "unknown"))
        ended_at = meta.get("ended_at")

        if isinstance(ended_at, (int, float)):
            dt = datetime.fromtimestamp(ended_at)
            timestamp = dt.strftime("%Y%m%d_%H%M%S")
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        filename = "{0}_{1}.json".format(timestamp, session_id[:8])
        target = self._base_dir / filename

        try:
            if self.config.archive_pretty:
                content = json.dumps(session_payload, ensure_ascii=False, indent=2)
            else:
                content = json.dumps(session_payload, ensure_ascii=False, separators=(",", ":"))
            target.write_text(content + "\n", encoding="utf-8")
        except OSError as exc:
            self._last_error = "Failed to save session archive: {0}".format(exc)
            self.logger.warning(self._last_error)
            return None

        self._saved_count += 1
        self._last_saved_path = str(target)
        self._last_error = None
        return {
            "path": str(target),
            "filename": filename,
            "saved_at": datetime.now().isoformat(),
        }
