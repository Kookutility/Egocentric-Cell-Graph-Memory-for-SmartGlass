# DemoIndoorScene setup guide

## Recommended hierarchy

- `DemoIndoorScene`
  - `Directional Light`
  - `EnvironmentRoot`
    - corridor segments
    - room modules
    - door prefabs
    - small open-space modules
    - decision intersections
  - `PlayerRig`
    - `CharacterController`
    - `PlayerController`
    - `ImuSimulator`
    - `SensorCapture`
    - `PythonBridge`
    - `MainCamera`
  - `UICanvas`
    - instruction label
    - cell id label
    - cell type label
    - event label
    - confidence label
    - status label
    - graph summary label
    - buttons: start/reset/stop/backtrack

## Suggested test path

1. Start in a corridor.
2. Move through a doorway into a room.
3. Exit to a decision point.
4. Turn right into another corridor segment.
5. Trigger backtracking and verify the reversed instruction sequence.

## Wiring notes

- Assign the `MainCamera` to `SensorCapture`.
- Assign `ImuSimulator` and `SensorCapture` to `PythonBridge`.
- Assign `PythonBridge` to `NavigationUI`, `DebugGraphView`, and `SessionController`.
- Use TextMeshProUGUI fields for UI labels.
