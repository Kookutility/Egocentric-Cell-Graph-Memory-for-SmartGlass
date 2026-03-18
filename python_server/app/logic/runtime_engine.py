"""Main per-frame runtime engine tying together vision, FSM, graph, and instructions."""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass

import cv2
import numpy as np

from app.config import CONFIG
from app.logic.event_parser import EventParser
from app.logic.imu_processor import ImuProcessor
from app.logic.instruction_generator import instruction_for_transition
from app.logic.relocalizer import Relocalizer
from app.logic.step_estimator import StepEstimator
from app.schemas import FramePacket, GraphSummary, RelocCandidate, ResultPacket, VisionOutput
from app.state.cell_graph import CellGraph
from app.vision.corridor_axis_detector import CorridorAxisDetector
from app.vision.detector_frontend import DetectorFrontend
from app.vision.optical_flow import OpticalFlowFrontend
from app.vision.scene_classifier import SceneClassifier, ScenePrediction
from app.vision.tracker_frontend import TrackerFrontend
from app.vision.vlm_arbiter import VlmArbiter


@dataclass(slots=True)
class _VisionCache:
    detections: list = None
    scene: ScenePrediction | None = None
    detector_frame: int = -1
    scene_frame: int = -1

    def __post_init__(self) -> None:
        if self.detections is None:
            self.detections = []


class RuntimeEngine:
    """Processes streamed Unity packets into qualitative navigation outputs."""

    def __init__(self) -> None:
        self.detector = DetectorFrontend()
        self.tracker = TrackerFrontend()
        self.scene_classifier = SceneClassifier()
        self.axis_detector = CorridorAxisDetector()
        self.flow = OpticalFlowFrontend()
        self.vlm = VlmArbiter()
        self.imu = ImuProcessor()
        self.steps = StepEstimator()
        self.events = EventParser()
        self.relocalizer = Relocalizer()
        self.reset()

    def reset(self) -> None:
        """Resets all session-scoped caches so a new session starts cleanly."""

        self.detector = DetectorFrontend(self.detector.model_path)
        self.tracker = TrackerFrontend()
        self.scene_classifier = SceneClassifier()
        self.axis_detector = CorridorAxisDetector()
        self.flow = OpticalFlowFrontend()
        self.vlm.reset()
        self.imu = ImuProcessor()
        self.steps = StepEstimator()
        self.events = EventParser()
        self.relocalizer.reset()
        self._last_boundary_distance_m = 0.0
        self._last_boundary_step_count = 0
        self._frame_counter = 0
        self._vision_cache = _VisionCache()
        self._recent_gray: np.ndarray | None = None
        self._cached_candidates: list[RelocCandidate] = []
        self._low_confidence_streak = 0
        self._scene_ambiguity_streak = 0
        self._backtrack_cursor = 0
        self._backtracking_active = False

    @staticmethod
    def _decode_frame(jpg_b64: str) -> np.ndarray:
        raw = base64.b64decode(jpg_b64)
        arr = np.frombuffer(raw, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("Failed to decode jpg_b64 frame")
        return frame

    def _compute_frame_similarity(self, frame_bgr: np.ndarray) -> float:
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        if self._recent_gray is None:
            self._recent_gray = gray
            return 1.0
        diff = cv2.absdiff(self._recent_gray, gray)
        self._recent_gray = gray
        mean_diff = float(diff.mean()) / 255.0
        return max(0.0, 1.0 - mean_diff)

    def _vision_pass(self, frame_bgr: np.ndarray) -> tuple[VisionOutput, dict[str, bool]]:
        """Runs cheap vision every frame and samples heavy inference on configurable intervals."""

        self._frame_counter += 1
        sampled_detector = self._frame_counter == 1 or self._frame_counter % CONFIG.detector_interval_frames == 0
        sampled_scene = self._frame_counter == 1 or self._frame_counter % CONFIG.scene_classifier_interval_frames == 0

        if sampled_detector:
            detections = self.detector.infer(frame_bgr)
            tracked = self.tracker.update(detections)
            self._vision_cache.detections = tracked
            self._vision_cache.detector_frame = self._frame_counter
        else:
            tracked = self.tracker.active_tracks() or self._vision_cache.detections

        if sampled_scene or self._vision_cache.scene is None:
            scene = self.scene_classifier.infer(frame_bgr)
            self._vision_cache.scene = scene
            self._vision_cache.scene_frame = self._frame_counter
        else:
            scene = self._vision_cache.scene

        axis = self.axis_detector.infer(frame_bgr)
        flow = self.flow.infer(frame_bgr)
        frame_similarity = self._compute_frame_similarity(frame_bgr)
        landmark_tokens = [det.label for det in tracked if det.label in {"exit_sign", "stair_entry", "elevator_door"}]
        text_tokens = [f"scene:{scene.label}"]
        return (
            VisionOutput(
                scene_label=scene.label,
                scene_confidence=scene.confidence,
                detections=tracked,
                axis_heading_deg=axis.axis_heading_deg,
                axis_confidence=axis.axis_confidence,
                corridor_end_confidence=axis.corridor_end_confidence,
                side_openings=axis.side_openings,
                forward_flow=flow.forward_flow,
                frame_similarity=frame_similarity,
                landmark_tokens=sorted(set(landmark_tokens)),
                text_tokens=text_tokens,
                vlm_used=False,
            ),
            {"detector": sampled_detector, "scene": sampled_scene},
        )

    def _should_run_relocalizer(self, decision_event: str, vision: VisionOutput) -> bool:
        return (
            self._frame_counter == 1
            or self._frame_counter % CONFIG.relocalizer_interval_frames == 0
            or decision_event in {"door_pass_event", "scene_change_confirmed", "decision_candidate", "turn_left", "turn_right"}
            or vision.scene_confidence < CONFIG.vlm_trigger_conf
        )

    def _maybe_relocalize(self, graph: CellGraph, current_cell, recent_transitions: list[str], decision_event: str, vision: VisionOutput) -> list[RelocCandidate]:
        if self._should_run_relocalizer(decision_event, vision):
            self._cached_candidates = [
                RelocCandidate(cell_id=c.cell_id, score=c.score)
                for c in self.relocalizer.score_candidates(graph, current_cell, recent_transitions)
            ]
        return self._cached_candidates

    def _maybe_run_vlm(self, vision: VisionOutput, decision, candidates: list[RelocCandidate]) -> tuple[bool, list[str]]:
        reasons: list[str] = []
        if vision.scene_confidence < CONFIG.vlm_trigger_conf:
            self._low_confidence_streak += 1
            reasons.append("scene_low_conf")
        else:
            self._low_confidence_streak = 0

        door_detections = [det for det in vision.detections if det.label == "door"]
        if len(door_detections) > 1:
            reasons.append("doorway_ambiguity")

        if len(candidates) >= 2 and candidates[0].score - candidates[1].score < CONFIG.relocalizer_top2_gap_th:
            reasons.append("relocalization_gap_small")

        if decision.event in {"door_candidate", "door_occluded", "decision_candidate"} or vision.scene_label == "decision_area":
            self._scene_ambiguity_streak += 1
        else:
            self._scene_ambiguity_streak = 0
        if self._scene_ambiguity_streak >= CONFIG.ambiguity_persist_frames:
            reasons.append("persistent_ambiguity")

        vlm_decision = self.vlm.maybe_arbitrate(sorted(set(reasons)), vision.scene_confidence)
        if vlm_decision.used:
            if vlm_decision.label_override:
                vision.scene_label = vlm_decision.label_override
            if vlm_decision.landmark_tokens:
                vision.landmark_tokens = sorted(set(vision.landmark_tokens + vlm_decision.landmark_tokens))
            vision.vlm_used = True
        return vision.vlm_used, vlm_decision.reasons

    def _backtrack_instruction(self, graph: CellGraph):
        reverse_edge = graph.reverse_edge_at(self._backtrack_cursor)
        if reverse_edge is None:
            return instruction_for_transition(None, None), "backtrack_complete", 0.5, None
        while self._backtrack_cursor + 1 < len(graph.edges) and graph.current_cell_id == reverse_edge.from_cell:
            self._backtrack_cursor += 1
            reverse_edge = graph.reverse_edge_at(self._backtrack_cursor)
            if reverse_edge is None:
                break
        if reverse_edge is None:
            return instruction_for_transition(None, None), "backtrack_complete", 0.5, None
        instruction = instruction_for_transition(reverse_edge.transition_type, reverse_edge.exit_side)
        event = f"backtrack_{reverse_edge.transition_type}"
        return instruction, event, reverse_edge.confidence, reverse_edge

    def process(self, packet: FramePacket, graph: CellGraph, fsm, recent_transitions: list[str], backtracking: bool) -> ResultPacket:
        frame_bgr = self._decode_frame(packet.jpg_b64)
        imu_state = self.imu.update(packet.yaw_deg)
        step_state = self.steps.update(packet.timestamp, packet.step_count)
        distance_since_last_boundary = max(0.0, step_state.distance_m - self._last_boundary_distance_m)
        steps_since_last_boundary = max(0, step_state.step_count - self._last_boundary_step_count)

        vision, sample_flags = self._vision_pass(frame_bgr)
        decision = self.events.update(packet.timestamp, frame_bgr.shape[1], imu_state, vision, distance_since_last_boundary)
        fsm_state = fsm.update(packet.timestamp, imu_state, vision, decision)

        current_cell = graph.update_current_cell(
            frame_id=packet.frame_id,
            step_span=steps_since_last_boundary,
            distance_span_m=distance_since_last_boundary,
            confidence=decision.confidence or vision.scene_confidence,
            corridor_axis_heading_deg=vision.axis_heading_deg,
            landmark_tokens=vision.landmark_tokens,
            text_tokens=vision.text_tokens,
            door_side=decision.door_side,
        )

        transition_type = decision.transition_type
        if decision.create_new_cell and fsm_state == "NEW_CELL":
            graph.create_boundary(
                transition_type=transition_type or "straight_continue",
                cell_type=decision.cell_type_hint,
                heading_deg=imu_state.smoothed_yaw_deg,
                exit_side=decision.door_side,
                turn_angle_deg=decision.turn_angle_deg,
                step_count=steps_since_last_boundary,
                distance_m=distance_since_last_boundary,
                total_step_count=step_state.step_count,
                total_distance_m=step_state.distance_m,
                confidence=decision.confidence,
                frame_id=packet.frame_id,
                corridor_axis_heading_deg=vision.axis_heading_deg,
                landmark_tokens=vision.landmark_tokens,
                text_tokens=vision.text_tokens,
            )
            self._last_boundary_distance_m = step_state.distance_m
            self._last_boundary_step_count = step_state.step_count
            self.events.mark_boundary_created(packet.timestamp)
            if transition_type:
                recent_transitions.append(transition_type)
                del recent_transitions[:-5]
            current_cell = graph.cells[graph.current_cell_id]

        relocalizer_sampled = self._should_run_relocalizer(decision.event, vision)
        candidates = self._maybe_relocalize(graph, current_cell, recent_transitions, decision.event, vision)
        vlm_used, vlm_reasons = self._maybe_run_vlm(vision, decision, candidates)

        if backtracking and graph.edges:
            if not self._backtracking_active:
                self._backtracking_active = True
                self._backtrack_cursor = 0
            instruction, event, confidence, reverse_edge = self._backtrack_instruction(graph)
            if reverse_edge is not None and graph.current_cell_id == reverse_edge.from_cell and self._backtrack_cursor + 1 < len(graph.edges):
                self._backtrack_cursor += 1
        else:
            self._backtracking_active = False
            instruction = instruction_for_transition(transition_type, decision.door_side)
            event = decision.event
            confidence = max(decision.confidence, vision.scene_confidence)

        return ResultPacket(
            frame_id=packet.frame_id,
            fsm_state=fsm_state,
            cell_id=graph.current_cell_id,
            cell_type=graph.cells[graph.current_cell_id].cell_type,
            event=event,
            instruction=instruction,
            confidence=round(confidence, 3),
            graph_summary=GraphSummary(**graph.summary()),
            debug={
                "scene_label": vision.scene_label,
                "scene_confidence": round(vision.scene_confidence, 3),
                "axis_confidence": round(vision.axis_confidence, 3),
                "forward_flow": round(vision.forward_flow, 3),
                "frame_similarity": round(vision.frame_similarity, 3),
                "yaw_delta_deg": round(imu_state.yaw_delta_deg, 3),
                "accumulated_turn_deg": round(imu_state.accumulated_turn_deg, 3),
                "detector_sampled": sample_flags["detector"],
                "scene_sampled": sample_flags["scene"],
                "distance_since_last_boundary_m": round(distance_since_last_boundary, 3),
                "steps_since_last_boundary": steps_since_last_boundary,
                "relocalizer_sampled": relocalizer_sampled,
                "vlm_reasons": vlm_reasons,
                "runtime_ts": time.time(),
                **decision.debug,
            },
            top_candidates=candidates,
            vlm_used=vlm_used,
        )
