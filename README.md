# Smart-Glass Indoor Backtracking Prototype

This repository contains a **SLAM-free Unity + Python prototype** for indoor backtracking on smart-glass style hardware simulation.

The prototype is intentionally organized around a **qualitative cell graph** instead of a metric map. Unity streams RGB frames and IMU-style yaw to a FastAPI runtime, and the Python runtime incrementally builds a route memory, emits Korean navigation instructions, and exports logs for analysis.

## Project layout

```text
Assets/
  Scripts/
    Sensor/
    Network/
    UI/
    Player/
    Debug/
  Scenes/
  Prefabs/
  Materials/
  Resources/
python_server/
  app/
  example_packets/
  models/
  outputs/
  requirements.txt
```

## Key design constraints

- No full SLAM.
- No metric map reconstruction.
- New cells are **never** created from scene similarity alone.
- Navigation is based on:
  - turn events,
  - door-pass events,
  - decision points,
  - qualitative scene/corridor cues,
  - transition history for relocalization.

## Python server quick start

```bash
cd python_server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.server:app --host 127.0.0.1 --port 8000
```

## Unity runtime flow

1. Open or create a Unity 6.x project rooted at this repository.
2. Create the folder structure shown above if Unity has not already imported it.
3. Create `DemoIndoorScene`.
4. Add a `PlayerRig` GameObject containing:
   - `CharacterController`
   - `PlayerController`
   - child `MainCamera`
   - `ImuSimulator`
   - `SensorCapture`
   - `PythonBridge`
5. Add a `Canvas` with TextMeshPro labels and wire them to:
   - `NavigationUI`
   - `DebugGraphView`
   - `SessionController`
6. Start the Python server.
7. Play the Unity scene.
8. Use the UI buttons to start/reset/stop/backtrack the session.

Detailed setup notes are in `Assets/Scenes/DemoIndoorScene.md`.

For a full Korean step-by-step install/run guide, see `docs/SETUP_KO.md`.

## HTTP endpoints

- `POST /session/start`
- `POST /session/reset`
- `POST /session/stop`
- `GET /session/status`
- `POST /session/backtrack`
- `GET /session/export/{session_id}`

## WebSocket endpoint

- `ws://127.0.0.1:8000/ws/runtime`

Unity sends `FramePacket` JSON messages and receives `ResultPacket` JSON messages.

## Example packets

See:
- `python_server/example_packets/frame_packet.json`
- `python_server/example_packets/result_packet.json`

## Implementation notes

### Phase coverage

This repository provides a **minimal runnable end-to-end prototype scaffold** covering:

- session lifecycle management,
- real-time WebSocket packet loop,
- qualitative cell graph updates,
- finite-state transitions,
- Korean backtracking instruction generation,
- export of graph/results/events,
- Unity integration scripts for capture/network/UI.

The vision stack is intentionally implemented with graceful degradation:

- if model weights are available locally, wrappers can load them,
- otherwise heuristic frontends keep the demo operational.

### Model hooks

The code includes extension points for:

- YOLO11n detector frontend,
- ByteTrack-style tracking frontend,
- MobileOne-S1 scene classifier frontend,
- SmolVLM arbitration hooks.

These modules are kept separate so you can replace heuristic logic with production models without changing the HTTP/WebSocket protocol.

## Demo checklist

- [x] Unity streams RGB + yaw + optional step count.
- [x] Python maintains online session state.
- [x] Cell graph updates only on approved boundary rules.
- [x] Backtracking reverses traversed edges.
- [x] Unity UI can display instruction, cell, event, confidence, and connection state.

## Limitations

- Unity scene content is documented and scripted, but an actual `.unity` binary scene asset is not generated in this text-only environment.
- Deep learning model weights are not bundled in the repo.
- The default runtime uses heuristic fallbacks when weights are unavailable.
