"""Main per-frame runtime engine tying together vision, FSM, graph, and instructions."""

from __future__ import annotations

import base64
import time

import cv2
import numpy as np

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
from app.vision.scene_classifier import SceneClassifier
from app.vision.tracker_frontend import TrackerFrontend
from app.vision.vlm_arbiter import VlmArbiter


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
        self._last_boundary_distance_m = 0.0

    @staticmethod
    def _decode_frame(jpg_b64: str) -> np.ndarray:
        raw = base64.b64decode(jpg_b64)
        arr = np.frombuffer(raw, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("Failed to decode jpg_b64 frame")
        return frame

    def _vision_pass(self, frame_bgr: np.ndarray) -> VisionOutput:
        detections = self.tracker.update(self.detector.infer(frame_bgr))
        scene = self.scene_classifier.infer(frame_bgr)
        axis = self.axis_detector.infer(frame_bgr)
        flow = self.flow.infer(frame_bgr)
        landmark_tokens = [det.label for det in detections if det.label in {"exit_sign", "stair_entry", "elevator_door"}]
        text_tokens = [f"scene:{scene.label}"]
        vlm = self.vlm.maybe_arbitrate("scene_low_conf", scene.confidence)
        if vlm.label_override:
            scene.label = vlm.label_override
        if vlm.landmark_tokens:
            landmark_tokens.extend(vlm.landmark_tokens)
        return VisionOutput(
            scene_label=scene.label,
            scene_confidence=scene.confidence,
            detections=detections,
            axis_heading_deg=axis.axis_heading_deg,
            axis_confidence=axis.axis_confidence,
            corridor_end_confidence=axis.corridor_end_confidence,
            side_openings=axis.side_openings,
            forward_flow=flow.forward_flow,
            landmark_tokens=sorted(set(landmark_tokens)),
            text_tokens=text_tokens,
            vlm_used=vlm.used,
        )

    def process(self, packet: FramePacket, graph: CellGraph, fsm, recent_transitions: list[str], backtracking: bool) -> ResultPacket:
        frame_bgr = self._decode_frame(packet.jpg_b64)
        imu_state = self.imu.update(packet.yaw_deg)
        step_state = self.steps.update(packet.timestamp, packet.step_count)
        distance_since_last_boundary = max(0.0, step_state.distance_m - self._last_boundary_distance_m)
        vision = self._vision_pass(frame_bgr)
        decision = self.events.update(packet.timestamp, frame_bgr.shape[1], imu_state, vision, distance_since_last_boundary)
        fsm_state = fsm.update(packet.timestamp, imu_state, vision, decision)

        current_cell = graph.update_current_cell(
            frame_id=packet.frame_id,
            step_span=step_state.step_count,
            confidence=decision.confidence or vision.scene_confidence,
            corridor_axis_heading_deg=vision.axis_heading_deg,
            landmark_tokens=vision.landmark_tokens,
            text_tokens=vision.text_tokens,
            door_side=decision.door_side,
        )

        transition_type = decision.transition_type
        if decision.create_new_cell and fsm_state in {"NEW_CELL", "CONFIRM_BOUNDARY"}:
            graph.create_boundary(
                transition_type=transition_type or "straight_continue",
                cell_type=decision.cell_type_hint,
                heading_deg=imu_state.smoothed_yaw_deg,
                exit_side=decision.door_side,
                turn_angle_deg=decision.turn_angle_deg,
                step_count=step_state.step_count,
                confidence=decision.confidence,
                frame_id=packet.frame_id,
                corridor_axis_heading_deg=vision.axis_heading_deg,
                landmark_tokens=vision.landmark_tokens,
                text_tokens=vision.text_tokens,
            )
            self._last_boundary_distance_m = step_state.distance_m
            if transition_type:
                recent_transitions.append(transition_type)
                del recent_transitions[:-5]
            current_cell = graph.cells[graph.current_cell_id]

        candidates = [RelocCandidate(cell_id=c.cell_id, score=c.score) for c in self.relocalizer.score_candidates(graph, current_cell, recent_transitions)]

        if backtracking and graph.edges:
            reverse_edge = graph.reverse_edges()[0]
            instruction = instruction_for_transition(reverse_edge.transition_type, reverse_edge.exit_side)
            event = f"backtrack_{reverse_edge.transition_type}"
            confidence = reverse_edge.confidence
        else:
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
                "yaw_delta_deg": round(imu_state.yaw_delta_deg, 3),
                "accumulated_turn_deg": round(imu_state.accumulated_turn_deg, 3),
                "runtime_ts": time.time(),
                **decision.debug,
            },
            top_candidates=candidates,
            vlm_used=vision.vlm_used,
        )
