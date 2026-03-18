"""FastAPI server for the smart-glass indoor backtracking prototype."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse

from app.config import CONFIG
from app.io.export import export_json
from app.io.session_store import SESSION_STORE
from app.logic.runtime_engine import RuntimeEngine
from app.schemas import FramePacket, SessionControlResponse, SessionStartRequest, SessionStatusResponse

app = FastAPI(title="SmartGlass Backtracking Prototype", version="0.1.0")
engine = RuntimeEngine()


def _require_runtime():
    runtime = SESSION_STORE.runtime
    if runtime is None:
        raise HTTPException(status_code=404, detail="No active session")
    return runtime


@app.post("/session/start", response_model=SessionControlResponse)
def start_session(payload: SessionStartRequest) -> SessionControlResponse:
    runtime = SESSION_STORE.start(payload.session_id)
    return SessionControlResponse(ok=True, session_id=runtime.session_id, message="session started")


@app.post("/session/reset", response_model=SessionControlResponse)
def reset_session() -> SessionControlResponse:
    runtime = SESSION_STORE.reset()
    if runtime is None:
        raise HTTPException(status_code=404, detail="No active session")
    return SessionControlResponse(ok=True, session_id=runtime.session_id, message="session reset")


@app.post("/session/stop", response_model=SessionControlResponse)
def stop_session() -> SessionControlResponse:
    runtime = SESSION_STORE.stop()
    if runtime is None:
        raise HTTPException(status_code=404, detail="No active session")
    export_json(runtime.output_dir / "graph.json", runtime.graph.export())
    return SessionControlResponse(
        ok=True,
        session_id=runtime.session_id,
        message="session stopped",
        export_path=str(runtime.output_dir),
    )


@app.get("/session/status", response_model=SessionStatusResponse)
def session_status() -> SessionStatusResponse:
    runtime = SESSION_STORE.runtime
    if runtime is None:
        return SessionStatusResponse(session_id=None, active=False, backtracking=False, latest_frame_id=None, latest_result=None)
    return SessionStatusResponse(
        session_id=runtime.session_id,
        active=runtime.active,
        backtracking=runtime.backtracking,
        latest_frame_id=runtime.latest_frame_id,
        latest_result=runtime.latest_result,
    )


@app.post("/session/backtrack", response_model=SessionControlResponse)
def trigger_backtrack() -> SessionControlResponse:
    runtime = _require_runtime()
    runtime.backtracking = True
    return SessionControlResponse(ok=True, session_id=runtime.session_id, message="backtracking enabled")


@app.get("/session/export/{session_id}")
def export_session(session_id: str):
    output_dir = CONFIG.output_root / session_id
    graph_path = output_dir / "graph.json"
    if not graph_path.exists():
        raise HTTPException(status_code=404, detail="Export not found")
    return FileResponse(graph_path)


@app.websocket("/ws/runtime")
async def runtime_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    runtime = _require_runtime()
    try:
        while True:
            payload = await websocket.receive_json()
            packet = FramePacket.model_validate(payload)
            runtime.latest_frame_id = packet.frame_id
            result = engine.process(packet, runtime.graph, runtime.fsm, runtime.recent_transitions, runtime.backtracking)
            runtime.latest_result = result
            runtime.logger.log_event({"frame_id": packet.frame_id, "event": result.event, "fsm_state": result.fsm_state})
            runtime.logger.log_result(result.model_dump())
            await websocket.send_json(result.model_dump())
    except WebSocketDisconnect:
        return
    except Exception as exc:
        await websocket.send_json({"error": str(exc)})
        await websocket.close()


@app.get("/")
def root() -> JSONResponse:
    return JSONResponse({
        "message": "SmartGlass Backtracking Prototype",
        "session_status": "/session/status",
        "websocket": f"ws://{CONFIG.host}:{CONFIG.port}/ws/runtime",
    })
