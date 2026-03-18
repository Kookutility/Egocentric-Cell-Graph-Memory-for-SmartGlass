"""Rate-limited optional VLM arbitration hook."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.config import CONFIG


@dataclass(slots=True)
class VlmDecision:
    used: bool
    label_override: str | None = None
    landmark_tokens: list[str] | None = None
    reasons: list[str] = field(default_factory=list)


class VlmArbiter:
    """Stub hook for rare ambiguity handling outside the hot loop."""

    def __init__(self) -> None:
        self._last_used_ts = 0.0

    def reset(self) -> None:
        self._last_used_ts = 0.0

    def maybe_arbitrate(self, reasons: list[str], scene_confidence: float) -> VlmDecision:
        """Only arbitrates when explicit ambiguity reasons are present and rate limits allow it."""

        if not reasons:
            return VlmDecision(used=False)
        now = time.monotonic()
        if scene_confidence >= CONFIG.vlm_trigger_conf and "scene_low_conf" not in reasons:
            return VlmDecision(used=False, reasons=reasons)
        if now - self._last_used_ts < CONFIG.vlm_max_rate_s:
            return VlmDecision(used=False, reasons=reasons)
        self._last_used_ts = now
        return VlmDecision(used=True, label_override=None, landmark_tokens=sorted(set(reasons + ["ambiguous"])), reasons=reasons)
