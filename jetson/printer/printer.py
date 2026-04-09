from datetime import datetime, timezone
import json
from urllib import error, request
from uuid import uuid4

from ..utils.config import PrinterConfig


class Printer:
    """Sends print jobs to a Raspberry Pi print service or stdout."""

    def __init__(self, config: PrinterConfig) -> None:
        self.config = config

    def format_ticket(self, state: str, message: str) -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        return (
            "===========\n"
            "  OMIKUJI\n"
            "===========\n\n"
            f"STATE:\n{state.upper()}\n\n"
            f"MESSAGE:\n{message}\n\n"
            "-----------\n"
            f"{now}\n"
            "-----------"
        )

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

    def dispatch_print_job(self, payload):
        if self.config.transport == "stdout":
            print(payload["ticket_text"])
            return payload

        if self.config.transport == "http":
            self._send_http_job(payload)
            return payload

        raise ValueError(f"Unsupported printer transport: {self.config.transport}")

    def print_omikuji(self, state: str, message: str):
        payload = self.build_print_job(state, message)
        return self.dispatch_print_job(payload)
