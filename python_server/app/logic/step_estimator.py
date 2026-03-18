"""Step count handling and simple fallback estimation."""

from __future__ import annotations

from dataclasses import dataclass

from app.config import CONFIG


@dataclass(slots=True)
class StepState:
    step_count: int
    distance_m: float
    used_fallback: bool


class StepEstimator:
    """Uses Unity step counts when present, otherwise estimates from timestamps."""

    def __init__(self) -> None:
        self._step_count = 0
        self._last_timestamp: float | None = None

    def update(self, timestamp: float, step_count: int | None) -> StepState:
        if step_count is not None:
            self._step_count = step_count
            self._last_timestamp = timestamp
            return StepState(step_count=step_count, distance_m=step_count * CONFIG.step_length_est_m, used_fallback=False)
        if self._last_timestamp is None:
            self._last_timestamp = timestamp
            return StepState(step_count=self._step_count, distance_m=self._step_count * CONFIG.step_length_est_m, used_fallback=True)
        delta_t = timestamp - self._last_timestamp
        self._last_timestamp = timestamp
        if CONFIG.step_min_interval_s <= delta_t <= CONFIG.step_max_interval_s:
            self._step_count += 1
        return StepState(step_count=self._step_count, distance_m=self._step_count * CONFIG.step_length_est_m, used_fallback=True)
