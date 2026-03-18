"""Detector frontend with optional YOLO loading and heuristic fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from app.schemas import Detection

try:
    from ultralytics import YOLO
except Exception:  # pragma: no cover - optional dependency path
    YOLO = None  # type: ignore[assignment]


@dataclass(slots=True)
class DetectorFrontend:
    model_path: str | None = None

    def __post_init__(self) -> None:
        self._model: Any | None = None
        if self.model_path and YOLO is not None:
            try:
                self._model = YOLO(self.model_path)
            except Exception:
                self._model = None

    def infer(self, frame_bgr: np.ndarray) -> list[Detection]:
        if self._model is not None:
            result = self._model(frame_bgr, verbose=False)[0]
            detections: list[Detection] = []
            for box in result.boxes:
                xyxy = tuple(int(v) for v in box.xyxy[0].tolist())
                cls_id = int(box.cls[0].item())
                label = result.names.get(cls_id, str(cls_id))
                detections.append(Detection(label=label, confidence=float(box.conf[0].item()), bbox_xyxy=xyxy))
            return detections

        height, width = frame_bgr.shape[:2]
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 80, 160)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detections: list[Detection] = []
        for contour in contours[:10]:
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            if area < 1500:
                continue
            aspect = h / max(w, 1)
            label = "door" if 1.5 < aspect < 4.5 else "glass_front"
            confidence = min(0.95, 0.45 + area / float(width * height))
            detections.append(Detection(label=label, confidence=confidence, bbox_xyxy=(x, y, x + w, y + h)))
        return detections
