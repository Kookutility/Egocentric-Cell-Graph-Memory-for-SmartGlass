"""Scene classifier frontend with heuristic fallback for demo use."""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from app.config import CONFIG

try:
    import torch
    from torchvision import transforms
except Exception:  # pragma: no cover - optional dependency path
    torch = None  # type: ignore[assignment]
    transforms = None  # type: ignore[assignment]


@dataclass(slots=True)
class ScenePrediction:
    label: str
    confidence: float


class SceneClassifier:
    """Classifies coarse scene type and smooths over a vote window."""

    LABELS = ("corridor", "room", "open_space_small", "decision_area")

    def __init__(self) -> None:
        self._model: Any | None = None
        self._vote_window: deque[str] = deque(maxlen=CONFIG.scene_vote_window)

    def infer(self, frame_bgr: np.ndarray) -> ScenePrediction:
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 80, 180)
        edge_density = float(np.count_nonzero(edges)) / max(edges.size, 1)
        brightness = float(gray.mean()) / 255.0
        if edge_density > 0.10 and brightness < 0.55:
            label, confidence = "corridor", 0.72
        elif edge_density < 0.05 and brightness > 0.65:
            label, confidence = "open_space_small", 0.62
        elif edge_density > 0.08 and brightness > 0.55:
            label, confidence = "decision_area", 0.58
        else:
            label, confidence = "room", 0.60
        self._vote_window.append(label)
        vote = Counter(self._vote_window).most_common(1)[0][0]
        confidence = min(0.95, confidence + (0.05 if vote == label else -0.05))
        return ScenePrediction(label=vote, confidence=confidence)
