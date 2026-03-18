"""Rate-limited optional VLM arbitration hook."""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.config import CONFIG


@dataclass(slots=True)
class VlmDecision:
    used: bool
    label_override: str | None = None
    landmark_tokens: list[str] | None = None


class VlmArbiter:
    """Stub hook for rare ambiguity handling outside the hot loop."""

    def __init__(self) -> None:
        self._last_used_ts = 0.0

    def maybe_arbitrate(self, reason: str, scene_confidence: float) -> VlmDecision:
        now = time.monotonic()
        if scene_confidence >= CONFIG.vlm_trigger_conf:
            return VlmDecision(used=False)
        if now - self._last_used_ts < CONFIG.vlm_max_rate_s:
            return VlmDecision(used=False)
        self._last_used_ts = now
        return VlmDecision(used=True, label_override=None, landmark_tokens=[reason, "ambiguous"])
