from __future__ import annotations

from datetime import datetime

from ..utils.config import PrinterConfig


class Printer:
    """Placeholder printer output. Replace with ESC/POS or serial implementation."""

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

    def print_omikuji(self, state: str, message: str) -> None:
        ticket = self.format_ticket(state, message)
        print(ticket)
