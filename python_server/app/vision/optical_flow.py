"""Dense optical flow helper for forward motion estimation."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(slots=True)
class OpticalFlowResult:
    forward_flow: float


class OpticalFlowFrontend:
    """Maintains previous grayscale frame and estimates mean forward flow magnitude."""

    def __init__(self) -> None:
        self._prev_gray: np.ndarray | None = None

    def infer(self, frame_bgr: np.ndarray) -> OpticalFlowResult:
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        if self._prev_gray is None:
            self._prev_gray = gray
            return OpticalFlowResult(forward_flow=0.0)
        flow = cv2.calcOpticalFlowFarneback(self._prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        self._prev_gray = gray
        mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        return OpticalFlowResult(forward_flow=float(np.mean(mag)))
