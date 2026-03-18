"""Combines IMU, vision, and step context into qualitative events."""

from __future__ import annotations

from collections import defaultdict, deque

from app.config import CONFIG
from app.logic.imu_processor import ImuState
from app.schemas import Detection, EventDecision, VisionOutput


class EventParser:
    """Encodes door, turn, and decision-point logic with qualitative boundary rules."""

    def __init__(self) -> None:
        self._door_track_frames: defaultdict[int, int] = defaultdict(int)
        self._door_area_history: defaultdict[int, deque[float]] = defaultdict(lambda: deque(maxlen=3))
        self._last_boundary_timestamp = -1e9

    @staticmethod
    def _bbox_area(bbox: tuple[int, int, int, int]) -> float:
        x1, y1, x2, y2 = bbox
        return max(0, x2 - x1) * max(0, y2 - y1)

    @staticmethod
    def _door_side_from_bbox(detection: Detection, frame_width: int, heading_delta: float) -> str:
        center_x = (detection.bbox_xyxy[0] + detection.bbox_xyxy[2]) / 2.0
        normalized = center_x / max(frame_width, 1)
        theta = (normalized - 0.5) * 120 + heading_delta
        if abs(theta) < 30:
            return "front"
        if 30 <= theta <= 120:
            return "right"
        if -120 <= theta <= -30:
            return "left"
        return "back"

    def update(
        self,
        timestamp: float,
        frame_width: int,
        imu: ImuState,
        vision: VisionOutput,
        distance_since_last_boundary_m: float,
    ) -> EventDecision:
        if timestamp - self._last_boundary_timestamp < CONFIG.new_cell_cooldown_s:
            cooldown_active = True
        else:
            cooldown_active = False

        door_detection: Detection | None = None
        for detection in vision.detections:
            if detection.label != "door" or detection.confidence < CONFIG.door_conf_th or detection.track_id is None:
                continue
            center_x = ((detection.bbox_xyxy[0] + detection.bbox_xyxy[2]) / 2.0) / max(frame_width, 1)
            if not (CONFIG.door_center_x_min <= center_x <= CONFIG.door_center_x_max):
                continue
            self._door_track_frames[detection.track_id] += 1
            self._door_area_history[detection.track_id].append(self._bbox_area(detection.bbox_xyxy))
            if self._door_track_frames[detection.track_id] >= CONFIG.door_persist_frames:
                door_detection = detection
                break

        if door_detection is not None:
            history = self._door_area_history[door_detection.track_id]
            area_growth = (history[-1] / max(history[0], 1.0)) if len(history) >= 2 else 1.0
            door_side = self._door_side_from_bbox(door_detection, frame_width, imu.yaw_delta_deg)
            if (
                area_growth > CONFIG.door_growth_ratio
                and vision.forward_flow > CONFIG.door_forward_flow_th
                and abs(imu.yaw_delta_deg) < CONFIG.door_cross_yaw_limit_deg
                and not cooldown_active
            ):
                self._last_boundary_timestamp = timestamp
                return EventDecision(
                    event="door_pass_event",
                    transition_type="door_pass",
                    confidence=min(0.99, door_detection.confidence + 0.1),
                    door_side=door_side,
                    turn_angle_deg=imu.accumulated_turn_deg,
                    create_new_cell=True,
                    cell_type_hint="room" if vision.scene_label == "room" else "corridor_segment",
                    debug={"area_growth": round(area_growth, 3)},
                )
            return EventDecision(
                event="door_candidate",
                transition_type=None,
                confidence=door_detection.confidence,
                door_side=door_side,
                debug={"track_frames": self._door_track_frames[door_detection.track_id]},
            )

        if imu.strong_turn and imu.stable_heading and not cooldown_active:
            self._last_boundary_timestamp = timestamp
            transition_type = "turn_right" if imu.accumulated_turn_deg > 0 else "turn_left"
            return EventDecision(
                event=transition_type,
                transition_type=transition_type,
                confidence=min(0.95, abs(imu.accumulated_turn_deg) / 120.0),
                turn_angle_deg=imu.accumulated_turn_deg,
                create_new_cell=True,
                cell_type_hint="decision_point" if any(vision.side_openings.values()) else "corridor_segment",
            )

        decision_candidate = (
            vision.axis_confidence > CONFIG.corridor_axis_conf_th
            and (
                any(vision.side_openings.values())
                or (vision.corridor_end_confidence > CONFIG.corridor_end_conf_th and any(vision.side_openings.values()))
            )
        )
        if decision_candidate and not cooldown_active:
            self._last_boundary_timestamp = timestamp
            return EventDecision(
                event="decision_candidate",
                transition_type="branch_enter",
                confidence=max(vision.axis_confidence, vision.corridor_end_confidence),
                door_side="left" if vision.side_openings.get("left") else "right" if vision.side_openings.get("right") else None,
                create_new_cell=True,
                cell_type_hint="decision_point",
            )

        if (
            distance_since_last_boundary_m >= CONFIG.min_boundary_distance_m
            and vision.scene_confidence >= CONFIG.room_corridor_score_th
            and vision.scene_label != "corridor"
            and not cooldown_active
        ):
            self._last_boundary_timestamp = timestamp
            return EventDecision(
                event="scene_change_confirmed",
                transition_type="straight_continue",
                confidence=vision.scene_confidence,
                create_new_cell=True,
                cell_type_hint="open_space_small" if vision.scene_label == "open_space_small" else vision.scene_label,
            )

        if abs(imu.accumulated_turn_deg) >= CONFIG.turn_threshold_deg:
            return EventDecision(event="turn_candidate", confidence=0.55, debug={"accumulated_turn_deg": imu.accumulated_turn_deg})

        return EventDecision(event="none", confidence=0.25)
