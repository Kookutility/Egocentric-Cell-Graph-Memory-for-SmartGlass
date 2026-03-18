"""Simple tracking frontend inspired by ByteTrack-style persistence."""

from __future__ import annotations

from collections import defaultdict

from app.schemas import Detection


class TrackerFrontend:
    """Assigns stable-ish IDs by IoU and class label for prototype usage."""

    def __init__(self) -> None:
        self._next_id = 1
        self._tracks: dict[int, Detection] = {}
        self._track_age: defaultdict[int, int] = defaultdict(int)

    @staticmethod
    def _iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)
        iw = max(0, inter_x2 - inter_x1)
        ih = max(0, inter_y2 - inter_y1)
        inter = iw * ih
        union = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
        return inter / union if union else 0.0

    def update(self, detections: list[Detection]) -> list[Detection]:
        assigned: list[Detection] = []
        unmatched_tracks = set(self._tracks)
        for detection in detections:
            best_track: int | None = None
            best_iou = 0.0
            for track_id, tracked in self._tracks.items():
                if tracked.label != detection.label:
                    continue
                overlap = self._iou(tracked.bbox_xyxy, detection.bbox_xyxy)
                if overlap > best_iou:
                    best_iou = overlap
                    best_track = track_id
            if best_track is not None and best_iou > 0.3:
                detection.track_id = best_track
                self._tracks[best_track] = detection
                self._track_age[best_track] += 1
                unmatched_tracks.discard(best_track)
            else:
                detection.track_id = self._next_id
                self._tracks[self._next_id] = detection
                self._track_age[self._next_id] = 1
                self._next_id += 1
            assigned.append(detection)
        for track_id in unmatched_tracks:
            self._track_age[track_id] -= 1
            if self._track_age[track_id] <= 0:
                self._tracks.pop(track_id, None)
                self._track_age.pop(track_id, None)
        return assigned

    def track_age(self, track_id: int | None) -> int:
        return 0 if track_id is None else self._track_age.get(track_id, 0)
