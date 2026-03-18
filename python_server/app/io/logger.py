"""Simple JSONL session logger."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SessionLogger:
    """Writes append-only JSONL logs for events and results."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.events_path = self.output_dir / "events.jsonl"
        self.results_path = self.output_dir / "results.jsonl"

    def log_event(self, payload: dict[str, Any]) -> None:
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def log_result(self, payload: dict[str, Any]) -> None:
        with self.results_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
