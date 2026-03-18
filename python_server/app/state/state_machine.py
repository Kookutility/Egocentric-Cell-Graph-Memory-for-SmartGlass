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


class RuntimeStateMachine:
    """Implements the boundary confirmation FSM used by the cell graph runtime."""

    def __init__(self) -> None:
        self.snapshot = FsmSnapshot(state="IN_CELL")

    def update(self, timestamp: float, imu: ImuState, vision: VisionOutput, decision: EventDecision) -> str:
        state = self.snapshot.state
        if timestamp < self.snapshot.cooldown_until_ts:
            self.snapshot.state = "IN_CELL"
            self.snapshot.confirm_counter = 0
            return self.snapshot.state

        # FSM transition comments are kept explicit to make debugging and tuning easier.
        if decision.event == "door_candidate":
            state = "DOOR_CANDIDATE"
        elif decision.event == "turn_candidate":
            state = "TURN_CANDIDATE"
        elif decision.event == "decision_candidate":
            state = "DECISION_CANDIDATE"
        elif decision.create_new_cell:
            state = "CONFIRM_BOUNDARY"
            self.snapshot.confirm_counter += 1
            if self.snapshot.confirm_counter >= CONFIG.boundary_confirm_frames:
                state = "NEW_CELL"
                self.snapshot.cooldown_until_ts = timestamp + CONFIG.new_cell_cooldown_s
                self.snapshot.confirm_counter = 0
        else:
            if imu.strong_turn and imu.stable_heading:
                state = "TURN_CANDIDATE"
            elif vision.axis_confidence > CONFIG.corridor_axis_conf_th and any(vision.side_openings.values()):
                state = "DECISION_CANDIDATE"
            else:
                state = "IN_CELL"
                self.snapshot.confirm_counter = 0

        self.snapshot.state = state
        return state
