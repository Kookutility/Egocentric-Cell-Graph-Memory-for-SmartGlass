"""Central configuration for the smart-glass runtime."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class RuntimeConfig(BaseModel):
    """Configurable thresholds and scheduling knobs for the prototype runtime."""

    host: str = "127.0.0.1"
    port: int = 8000
    default_session_id: str = "demo_001"
    output_root: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[1] / "outputs")

    heading_smooth_window: int = 7
    turn_threshold_deg: float = 35.0
    turn_strong_deg: float = 75.0
    turn_uturn_deg: float = 150.0
    heading_stable_frames: int = 6
    turn_heading_stability_deg: float = 12.0

    step_length_est_m: float = 0.70
    step_min_interval_s: float = 0.35
    step_max_interval_s: float = 1.20
    min_cell_steps: int = 5
    min_boundary_distance_m: float = 3.0

    scene_vote_window: int = 9
    scene_change_sim_th: float = 0.65
    room_corridor_score_th: float = 0.60
    openspace_score_th: float = 0.55
    scene_change_persist_frames: int = 3

    vp_stability_window: int = 7
    vp_stability_th: float = 0.75
    corridor_axis_conf_th: float = 0.60
    corridor_end_conf_th: float = 0.60
    side_opening_persist_frames: int = 5
    decision_point_persist_frames: int = 3

    door_forward_flow_th: float = 1.5
    door_conf_th: float = 0.65
    door_center_x_min: float = 0.30
    door_center_x_max: float = 0.70
    door_persist_frames: int = 3
    door_growth_ratio: float = 1.4
    door_cross_yaw_limit_deg: float = 15.0

    person_door_iou_hold: float = 0.40
    occlusion_hold_time_s: float = 0.5

    new_cell_cooldown_s: float = 1.5
    boundary_cooldown_s: float = 1.5
    boundary_confirm_frames: int = 4

    detector_interval_frames: int = 4
    scene_classifier_interval_frames: int = 6
    relocalizer_interval_frames: int = 10
    relocalizer_top2_gap_th: float = 0.08

    vlm_trigger_conf: float = 0.50
    vlm_max_rate_s: float = 3.0
    ambiguity_persist_frames: int = 4


CONFIG = RuntimeConfig()
