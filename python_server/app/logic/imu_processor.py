"""IMU yaw smoothing and turn detection."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from app.config import CONFIG


@dataclass(slots=True)
class ImuState:
    yaw_deg: float
    smoothed_yaw_deg: float
    yaw_delta_deg: float
    accumulated_turn_deg: float
    strong_turn: bool
    stable_heading: bool


class ImuProcessor:
    """Processes Unity yaw values into stable heading and turn cues."""

    def __init__(self) -> None:
        self._yaw_window: deque[float] = deque(maxlen=CONFIG.heading_smooth_window)
        self._smoothed_history: deque[float] = deque(maxlen=CONFIG.heading_stable_frames)
        self._last_smoothed: float | None = None
        self._accumulated_turn: float = 0.0

    @staticmethod
    def _normalize_delta(delta: float) -> float:
        while delta > 180:
            delta -= 360
        while delta < -180:
            delta += 360
        return delta

    def update(self, yaw_deg: float) -> ImuState:
        self._yaw_window.append(yaw_deg)
        smoothed = sum(self._yaw_window) / len(self._yaw_window)
        if self._last_smoothed is None:
            delta = 0.0
        else:
            delta = self._normalize_delta(smoothed - self._last_smoothed)
        self._last_smoothed = smoothed
        self._accumulated_turn += delta
        self._smoothed_history.append(smoothed)
        stable_heading = False
        if len(self._smoothed_history) == self._smoothed_history.maxlen:
            stable_heading = max(self._smoothed_history) - min(self._smoothed_history) < 8.0
            if stable_heading:
                self._accumulated_turn *= 0.5
        strong_turn = abs(self._accumulated_turn) >= CONFIG.turn_strong_deg
        return ImuState(
            yaw_deg=yaw_deg,
            smoothed_yaw_deg=smoothed,
            yaw_delta_deg=delta,
            accumulated_turn_deg=self._accumulated_turn,
            strong_turn=strong_turn,
            stable_heading=stable_heading,
        )
