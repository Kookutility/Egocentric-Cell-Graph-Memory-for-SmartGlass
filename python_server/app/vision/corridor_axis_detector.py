"""Corridor axis estimation from line segments and vanishing trends."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import cv2
import numpy as np

from app.config import CONFIG


@dataclass(slots=True)
class CorridorAxisResult:
    axis_heading_deg: float | None
    axis_confidence: float
    corridor_end_confidence: float
    side_openings: dict[str, bool]


class CorridorAxisDetector:
    """Uses Hough line cues as a lightweight corridor structure proxy."""

    def __init__(self) -> None:
        self._history: deque[float] = deque(maxlen=CONFIG.vp_stability_window)
        self._left_opening_history: deque[bool] = deque(maxlen=CONFIG.side_opening_persist_frames)
        self._right_opening_history: deque[bool] = deque(maxlen=CONFIG.side_opening_persist_frames)

    def infer(self, frame_bgr: np.ndarray) -> CorridorAxisResult:
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 60, 180)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=60, minLineLength=40, maxLineGap=20)
        if lines is None:
            self._left_opening_history.append(False)
            self._right_opening_history.append(False)
            return CorridorAxisResult(None, 0.0, 0.0, {"left": False, "right": False})

        slopes: list[float] = []
        vertical_count = 0
        width = frame_bgr.shape[1]
        left_activity = 0
        right_activity = 0
        for entry in lines[:, 0, :]:
            x1, y1, x2, y2 = entry.tolist()
            dx = x2 - x1
            dy = y2 - y1
            if abs(dx) < 4:
                vertical_count += 1
                continue
            slope = dy / dx
            slopes.append(slope)
            cx = (x1 + x2) / 2
            if cx < width * 0.33:
                left_activity += 1
            elif cx > width * 0.66:
                right_activity += 1
        axis_heading = float(np.degrees(np.arctan(np.median(slopes)))) if slopes else 0.0
        self._history.append(axis_heading)
        stability = 1.0 if len(self._history) < 2 else max(0.0, 1.0 - np.std(list(self._history)) / 45.0)
        axis_confidence = min(1.0, 0.3 + 0.05 * len(slopes) + 0.3 * stability)
        corridor_end_confidence = min(1.0, vertical_count / 10.0)
        self._left_opening_history.append(left_activity < 2)
        self._right_opening_history.append(right_activity < 2)
        side_openings = {
            "left": sum(self._left_opening_history) >= CONFIG.side_opening_persist_frames,
            "right": sum(self._right_opening_history) >= CONFIG.side_opening_persist_frames,
        }
        return CorridorAxisResult(axis_heading, axis_confidence, corridor_end_confidence, side_openings)
