from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from pose_tracker.domain.filters import OneEuroConfig
from pose_tracker.domain.exercises.squat import SquatSettings
from pose_tracker.domain.view import ViewThresholds
from pose_tracker.domain.exercises.shoulder_press import ShoulderPressSettings
from pose_tracker.domain.exercises.push_up import PushUpSettings
from pose_tracker.domain.exercises.deadlift import DeadliftSettings
from pose_tracker.domain.exercises.curl import CurlSettings
from pose_tracker.domain.exercises.bench_press import BenchPressSettings
from pose_tracker.domain.exercises.lateral_raise import LateralRaiseSettings
from pose_tracker.domain.exercises.plank import PlankSettings
from pose_tracker.domain.exercises.angled_bench import DECLINE, INCLINE, AngledBenchSettings
from pose_tracker.domain.exercises.bent_over_row import BentOverRowSettings
from pose_tracker.domain.exercises.calf_raise import CalfRaiseSettings
from pose_tracker.domain.exercises.hip_thrust import HipThrustSettings
from pose_tracker.domain.exercises.lat_pulldown import CLOSE_GRIP, WIDE_GRIP, LatPulldownSettings

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
    curl: CurlSettings = CurlSettings()
    bench_press: BenchPressSettings = BenchPressSettings()
    lateral_raise: LateralRaiseSettings = LateralRaiseSettings()
    plank: PlankSettings = PlankSettings()
    snapshot_retention_ms: int = 75_000   # long enough for a plank hold
    snapshot_min_interval_ms: int = 100   # keep ~10 frames per second
    incline_press: AngledBenchSettings = INCLINE
    decline_press: AngledBenchSettings = DECLINE
    pulldown_wide: LatPulldownSettings = WIDE_GRIP
    pulldown_close: LatPulldownSettings = CLOSE_GRIP
    hip_thrust: HipThrustSettings = HipThrustSettings()
    bent_over_row: BentOverRowSettings = BentOverRowSettings()
    calf_raise: CalfRaiseSettings = CalfRaiseSettings()
    calibration_file: Path = Path("calibration.toml")
    llm_file: Path = Path("llm.toml")


@dataclass(frozen=True, slots=True)
class LlmSettings:
    """Chat assistant backend: any server that speaks the OpenAI chat-completions API."""

    base_url: str = "http://localhost:8080/v1"
    model: str = "local-model"
    api_key: str = ""
    timeout_s: float = 120.0
    temperature: float = 0.3
    max_tokens: int = 1024           # reply length cap; 0 = the server's default
    context_tokens: int = 2048       # the context size your server was started with
    max_tool_steps: int = 6          # rounds of tool calls allowed per question
    max_history_turns: int = 8       # earlier question/answer pairs sent with each request

    def __post_init__(self) -> None:
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError("base_url must start with http:// or https://")
        if not self.model.strip():
            raise ValueError("model must not be empty")
        if self.timeout_s <= 0:
            raise ValueError("timeout_s must be more than 0")
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError("temperature must be between 0 and 2")
        if self.max_tokens < 0:
            raise ValueError("max_tokens must be 0 or more")
        if self.context_tokens < 1024:
            raise ValueError("context_tokens must be at least 1024")
        if not 1 <= self.max_tool_steps <= 20:
            raise ValueError("max_tool_steps must be between 1 and 20")
        if not 1 <= self.max_history_turns <= 50:
            raise ValueError("max_history_turns must be between 1 and 50")

        