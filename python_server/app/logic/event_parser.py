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
        self._door_occluded_until: defaultdict[int, float] = defaultdict(float)
        self._last_boundary_timestamp = -1e9
        self._side_opening_history: deque[bool] = deque(maxlen=CONFIG.decision_point_persist_frames)
        self._corridor_end_history: deque[bool] = deque(maxlen=CONFIG.decision_point_persist_frames)
        self._scene_history: deque[str] = deque(maxlen=CONFIG.scene_change_persist_frames)
        self._scene_conf_history: deque[float] = deque(maxlen=CONFIG.scene_change_persist_frames)

    def mark_boundary_created(self, timestamp: float) -> None:
        """Records the last committed boundary and clears short-term confirmation windows."""

        self._last_boundary_timestamp = timestamp
        self._side_opening_history.clear()
        self._corridor_end_history.clear()
        self._scene_history.clear()
        self._scene_conf_history.clear()

    @staticmethod
    def _bbox_area(bbox: tuple[int, int, int, int]) -> float:
        x1, y1, x2, y2 = bbox
        return max(0, x2 - x1) * max(0, y2 - y1)

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
        union = EventParser._bbox_area(a) + EventParser._bbox_area(b) - inter
        return inter / union if union else 0.0

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
        cooldown_active = timestamp - self._last_boundary_timestamp < CONFIG.boundary_cooldown_s
        self._scene_history.append(vision.scene_label)
        self._scene_conf_history.append(vision.scene_confidence)

        side_opening_evidence = any(vision.side_openings.values())
        corridor_end_evidence = vision.corridor_end_confidence > CONFIG.corridor_end_conf_th
        self._side_opening_history.append(side_opening_evidence)
        self._corridor_end_history.append(corridor_end_evidence)

        person_detections = [d for d in vision.detections if d.label == "person"]
        door_candidates = [d for d in vision.detections if d.label == "door" and d.confidence >= CONFIG.door_conf_th and d.track_id is not None]

        for detection in door_candidates:
            center_x = ((detection.bbox_xyxy[0] + detection.bbox_xyxy[2]) / 2.0) / max(frame_width, 1)
            if not (CONFIG.door_center_x_min <= center_x <= CONFIG.door_center_x_max):
                continue
            self._door_track_frames[detection.track_id] += 1
            self._door_area_history[detection.track_id].append(self._bbox_area(detection.bbox_xyxy))
            occluded = any(self._iou(detection.bbox_xyxy, person.bbox_xyxy) >= CONFIG.person_door_iou_hold for person in person_detections)
            if occluded:
                self._door_occluded_until[detection.track_id] = max(
                    self._door_occluded_until[detection.track_id],
                    timestamp + CONFIG.occlusion_hold_time_s,
                )
                return EventDecision(
                    event="door_occluded",
                    confidence=detection.confidence,
                    door_side=self._door_side_from_bbox(detection, frame_width, imu.yaw_delta_deg),
                    boundary_reason="door_hold",
                    debug={"door_track_id": detection.track_id, "occluded": True},
                )

            if self._door_occluded_until[detection.track_id] > timestamp:
                return EventDecision(
                    event="door_occluded",
                    confidence=detection.confidence,
                    door_side=self._door_side_from_bbox(detection, frame_width, imu.yaw_delta_deg),
                    boundary_reason="door_hold",
                    debug={"door_track_id": detection.track_id, "hold_until": round(self._door_occluded_until[detection.track_id], 3)},
                )

            if self._door_track_frames[detection.track_id] < CONFIG.door_persist_frames:
                continue

            history = self._door_area_history[detection.track_id]
            area_growth = (history[-1] / max(history[0], 1.0)) if len(history) >= 2 else 1.0
            door_side = self._door_side_from_bbox(detection, frame_width, imu.yaw_delta_deg)
            if (
                area_growth > CONFIG.door_growth_ratio
                and vision.forward_flow > CONFIG.door_forward_flow_th
                and abs(imu.yaw_delta_deg) < CONFIG.door_cross_yaw_limit_deg
                and not cooldown_active
                and distance_since_last_boundary_m >= CONFIG.min_boundary_distance_m
            ):
                return EventDecision(
                    event="door_pass_event",
                    transition_type="door_pass",
                    confidence=min(0.99, detection.confidence + 0.1),
                    door_side=door_side,
                    turn_angle_deg=imu.accumulated_turn_deg,
                    create_new_cell=True,
                    cell_type_hint="room" if vision.scene_label == "room" else "corridor_segment",
                    boundary_reason="door_pass",
                    debug={"area_growth": round(area_growth, 3)},
                )
            return EventDecision(
                event="door_candidate",
                transition_type=None,
                confidence=detection.confidence,
                door_side=door_side,
                boundary_reason="door_pass",
                debug={"track_frames": self._door_track_frames[detection.track_id]},
            )

        occluded_track_ids = [track_id for track_id, hold_until in self._door_occluded_until.items() if hold_until > timestamp]
        if occluded_track_ids:
            return EventDecision(
                event="door_occluded",
                confidence=0.5,
                boundary_reason="door_hold",
                debug={"occluded_tracks": occluded_track_ids},
            )

        if imu.strong_turn and imu.stable_heading and not cooldown_active and distance_since_last_boundary_m >= CONFIG.min_boundary_distance_m:
            transition_type = "turn_right" if imu.accumulated_turn_deg > 0 else "turn_left"
            return EventDecision(
                event=transition_type,
                transition_type=transition_type,
                confidence=min(0.95, abs(imu.accumulated_turn_deg) / 120.0),
                turn_angle_deg=imu.accumulated_turn_deg,
                create_new_cell=True,
                cell_type_hint="decision_point" if any(vision.side_openings.values()) else "corridor_segment",
                boundary_reason=transition_type,
            )

        persistent_side_opening = sum(self._side_opening_history) >= CONFIG.decision_point_persist_frames
        persistent_corridor_end = sum(self._corridor_end_history) >= CONFIG.decision_point_persist_frames
        stable_heading_for_branch = imu.stable_heading or abs(imu.yaw_delta_deg) <= CONFIG.turn_heading_stability_deg
        decision_candidate = (
            vision.axis_confidence > CONFIG.corridor_axis_conf_th
            and stable_heading_for_branch
            and (persistent_side_opening or persistent_corridor_end)
        )
        if decision_candidate and not cooldown_active and distance_since_last_boundary_m >= CONFIG.min_boundary_distance_m:
            return EventDecision(
                event="decision_candidate",
                transition_type="branch_enter",
                confidence=max(vision.axis_confidence, vision.corridor_end_confidence),
                door_side="left" if vision.side_openings.get("left") else "right" if vision.side_openings.get("right") else None,
                create_new_cell=True,
                cell_type_hint="decision_point",
                boundary_reason="decision_point",
                debug={
                    "persistent_side_opening": persistent_side_opening,
                    "persistent_corridor_end": persistent_corridor_end,
                    "stable_heading_for_branch": stable_heading_for_branch,
                },
            )

        stable_scene_change = (
            len(self._scene_history) == self._scene_history.maxlen
            and len(set(self._scene_history)) == 1
            and self._scene_history[-1] != "corridor"
            and min(self._scene_conf_history) >= CONFIG.room_corridor_score_th
        )
        if stable_scene_change and not cooldown_active and distance_since_last_boundary_m >= CONFIG.min_boundary_distance_m:
            scene_label = self._scene_history[-1]
            return EventDecision(
                event="scene_change_confirmed",
                transition_type="straight_continue",
                confidence=min(self._scene_conf_history),
                create_new_cell=True,
                cell_type_hint="open_space_small" if scene_label == "open_space_small" else scene_label,
                boundary_reason=f"scene_change:{scene_label}",
            )

        if abs(imu.accumulated_turn_deg) >= CONFIG.turn_threshold_deg:
            return EventDecision(event="turn_candidate", confidence=0.55, debug={"accumulated_turn_deg": imu.accumulated_turn_deg})

        return EventDecision(event="none", confidence=0.25)
