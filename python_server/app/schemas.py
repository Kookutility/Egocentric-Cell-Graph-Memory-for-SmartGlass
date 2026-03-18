"""Pydantic schemas used by the API and runtime."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class GraphSummary(BaseModel):
    num_cells: int = 0
    num_edges: int = 0


class FramePacket(BaseModel):
    session_id: str
    frame_id: int
    timestamp: float
    yaw_deg: float
    step_count: int | None = None
    jpg_b64: str


class RelocCandidate(BaseModel):
    cell_id: int
    score: float


class ResultPacket(BaseModel):
    frame_id: int
    fsm_state: str
    cell_id: int
    cell_type: str
    event: str
    instruction: str
    confidence: float
    graph_summary: GraphSummary
    debug: dict[str, Any] = Field(default_factory=dict)
    top_candidates: list[RelocCandidate] = Field(default_factory=list)
    vlm_used: bool = False


class SessionStartRequest(BaseModel):
    session_id: str = "demo_001"


class SessionStatusResponse(BaseModel):
    session_id: str | None
    active: bool
    backtracking: bool
    latest_frame_id: int | None
    latest_result: ResultPacket | None = None


class SessionControlResponse(BaseModel):
    ok: bool
    session_id: str | None
    message: str
    export_path: str | None = None


class Detection(BaseModel):
    label: str
    confidence: float
    bbox_xyxy: tuple[int, int, int, int]
    track_id: int | None = None


class VisionOutput(BaseModel):
    scene_label: Literal["corridor", "room", "open_space_small", "decision_area"]
    scene_confidence: float
    detections: list[Detection] = Field(default_factory=list)
    axis_heading_deg: float | None = None
    axis_confidence: float = 0.0
    corridor_end_confidence: float = 0.0
    side_openings: dict[str, bool] = Field(default_factory=lambda: {"left": False, "right": False})
    forward_flow: float = 0.0
    landmark_tokens: list[str] = Field(default_factory=list)
    text_tokens: list[str] = Field(default_factory=list)
    vlm_used: bool = False


class EventDecision(BaseModel):
    event: str = "none"
    transition_type: str | None = None
    confidence: float = 0.0
    door_side: str | None = None
    turn_angle_deg: float = 0.0
    create_new_cell: bool = False
    cell_type_hint: str = "corridor_segment"
    debug: dict[str, Any] = Field(default_factory=dict)
