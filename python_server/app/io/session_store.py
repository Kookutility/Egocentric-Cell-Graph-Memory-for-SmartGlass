"""In-memory session storage for the runtime server."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.config import CONFIG
from app.io.logger import SessionLogger
from app.schemas import ResultPacket
from app.state.cell_graph import CellGraph
from app.state.state_machine import RuntimeStateMachine


@dataclass
class SessionRuntime:
    session_id: str
    active: bool = True
    backtracking: bool = False
    latest_frame_id: int | None = None
    latest_result: ResultPacket | None = None
    graph: CellGraph = field(default_factory=CellGraph)
    fsm: RuntimeStateMachine = field(default_factory=RuntimeStateMachine)
    recent_transitions: list[str] = field(default_factory=list)

    @property
    def output_dir(self) -> Path:
        return CONFIG.output_root / self.session_id

    @property
    def logger(self) -> SessionLogger:
        if not hasattr(self, "_logger"):
            self._logger = SessionLogger(self.output_dir)
        return self._logger


class SessionStore:
    """Singleton-like store used by HTTP and WebSocket handlers."""

    def __init__(self) -> None:
        self.runtime: SessionRuntime | None = None

    def start(self, session_id: str) -> SessionRuntime:
        self.runtime = SessionRuntime(session_id=session_id)
        return self.runtime

    def reset(self) -> SessionRuntime | None:
        if self.runtime is None:
            return None
        self.runtime = SessionRuntime(session_id=self.runtime.session_id)
        return self.runtime

    def stop(self) -> SessionRuntime | None:
        if self.runtime is None:
            return None
        self.runtime.active = False
        return self.runtime


SESSION_STORE = SessionStore()
