from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from pose_tracker.domain.filters import OneEuroConfig
from pose_tracker.domain.exercises.squat import SquatSettings
from pose_tracker.domain.view import ViewThresholds
from pose_tracker.domain.exercises.shoulder_press import ShoulderPressSettings
from pose_tracker.domain.exercises.push_up import PushUpSettings
from pose_tracker.domain.exercises.deadlift import DeadliftSettings

@dataclass(frozen=True, slots=True)
class AppConfig:
    camera_index: int = 0
    frame_width: int = 1280
    frame_height: int = 720
    mirror: bool = True
    model_path: Path = Path("models/pose_landmarker_full.task")
    min_detection_confidence: float = 0.5
    min_presence_confidence: float = 0.5
    min_tracking_confidence: float = 0.5
    visibility_threshold: float = 0.5
    window_name: str = "Pose Tracker"
    smoothing: OneEuroConfig = OneEuroConfig()
    view_thresholds: ViewThresholds = ViewThresholds()
    squat: SquatSettings = SquatSettings()
    shoulder_press: ShoulderPressSettings = ShoulderPressSettings()
    push_up: PushUpSettings = PushUpSettings()
    deadlift: DeadliftSettings = DeadliftSettings()
    sessions_dir: Path = Path("sessions")
    history_dir: Path = Path("history")
    snapshot_max_width: int = 640
    snapshot_quality: int = 80
    snapshot_retention_ms: int = 15_000