"""Helpers for exporting graph state and metadata."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def export_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
