"""Finite-state machine for qualitative boundary confirmation."""

from __future__ import annotations

from dataclasses import dataclass

from app.config import CONFIG
from app.logic.imu_processor import ImuState
from app.schemas import EventDecision, VisionOutput


@dataclass(slots=True)
class FsmSnapshot:
    state: str
    confirm_counter: int = 0
    cooldown_until_ts: float = 0.0
    pending_reason: str | None = None


class RuntimeStateMachine:
    """Implements the boundary confirmation FSM used by the cell graph runtime."""

    def __init__(self) -> None:
        self.snapshot = FsmSnapshot(state="IN_CELL")

    def update(self, timestamp: float, imu: ImuState, vision: VisionOutput, decision: EventDecision) -> str:
        state = self.snapshot.state
        if timestamp < self.snapshot.cooldown_until_ts:
            self.snapshot.state = "IN_CELL"
            self.snapshot.confirm_counter = 0
            self.snapshot.pending_reason = None
            return self.snapshot.state

        if decision.event in {"door_candidate", "door_occluded"} and not decision.create_new_cell:
            state = "DOOR_CANDIDATE"
            self.snapshot.confirm_counter = 0
            self.snapshot.pending_reason = decision.boundary_reason
        elif decision.event == "turn_candidate":
            state = "TURN_CANDIDATE"
            self.snapshot.confirm_counter = 0
            self.snapshot.pending_reason = None
        elif decision.event == "decision_candidate" and not decision.create_new_cell:
            state = "DECISION_CANDIDATE"
            self.snapshot.confirm_counter = 0
            self.snapshot.pending_reason = decision.boundary_reason
        elif decision.create_new_cell:
            state = "CONFIRM_BOUNDARY"
            if decision.boundary_reason == self.snapshot.pending_reason:
                self.snapshot.confirm_counter += 1
            else:
                self.snapshot.confirm_counter = 1
                self.snapshot.pending_reason = decision.boundary_reason
            if self.snapshot.confirm_counter >= CONFIG.boundary_confirm_frames:
                state = "NEW_CELL"
                self.snapshot.cooldown_until_ts = timestamp + CONFIG.boundary_cooldown_s
                self.snapshot.confirm_counter = 0
                self.snapshot.pending_reason = None
        else:
            if imu.strong_turn and imu.stable_heading:
                state = "TURN_CANDIDATE"
            elif vision.axis_confidence > CONFIG.corridor_axis_conf_th and any(vision.side_openings.values()):
                state = "DECISION_CANDIDATE"
            else:
                state = "IN_CELL"
            self.snapshot.confirm_counter = 0
            self.snapshot.pending_reason = None

        self.snapshot.state = state
        return state
