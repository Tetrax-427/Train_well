from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pose_factory import plank_pose, press_pose

from pose_tracker.application.exercise_analyzer import ExerciseAnalyzer
from pose_tracker.domain.exercises.plank import build_plank
from pose_tracker.domain.pose import Pose
from pose_tracker.domain.view import StableViewDetector, ViewDetector

STANDING = press_pose(120)  # an upright body: far too steep to count as a plank


def make_analyzer() -> ExerciseAnalyzer:
    return ExerciseAnalyzer(
        build_plank(), StableViewDetector(ViewDetector(), frames_to_switch=1)
    )


def run_frames(frames: list[Pose | None]) -> ExerciseAnalyzer:
    analyzer = make_analyzer()
    for i, frame in enumerate(frames):
        analyzer.update(frame, i * 100, 1.0)
    return analyzer


def run(
    hold_frames: int = 80, pose_args: Callable[[int], dict[str, Any]] = lambda _i: {}
) -> ExerciseAnalyzer:
    """Stand, hold a plank for ``hold_frames`` frames (100 ms each), then stand again."""
    hold = [plank_pose(**pose_args(i)) for i in range(hold_frames)]
    return run_frames([STANDING] * 3 + hold + [STANDING] * 3)


def violations(analyzer: ExerciseAnalyzer) -> list[str]:
    assert len(analyzer.results) == 1
    return [v.rule_id for v in analyzer.results[0].violations]


def test_a_clean_hold_is_one_clean_rep_lasting_the_hold() -> None:
    analyzer = run()
    assert len(analyzer.results) == 1
    assert analyzer.results[0].is_clean
    assert analyzer.results[0].rep.duration_ms == 8000


def test_a_hold_that_is_too_short_is_not_counted() -> None:
    assert run(hold_frames=30).results == ()


def test_sagging_hips() -> None:
    assert violations(run(pose_args=lambda _i: {"hip_sag_deg": 20.0})) == ["hip_sag"]


def test_raised_hips() -> None:
    assert violations(run(pose_args=lambda _i: {"hip_sag_deg": -20.0})) == ["hip_pike"]


def test_bent_knees() -> None:
    assert "knee_bend" in violations(run(pose_args=lambda _i: {"knee_angle_deg": 130.0}))


def test_dropped_head() -> None:
    assert violations(run(pose_args=lambda _i: {"neck_angle_deg": 120.0})) == ["head_position"]


def test_elbows_not_under_the_shoulders() -> None:
    assert violations(run(pose_args=lambda _i: {"elbow_ahead": 0.6})) == ["support_position"]


def test_bobbing_hips() -> None:
    bob = lambda i: {"hip_sag_deg": 9.0 if i % 2 else 0.0}  # noqa: E731
    assert violations(run(pose_args=bob)) == ["hold_steady"]


def test_standing_up_is_never_a_plank() -> None:
    assert run_frames([STANDING] * 100).results == ()


def test_the_running_hold_time_is_reported() -> None:
    analyzer = make_analyzer()
    status = None
    for i, frame in enumerate([STANDING] * 3 + [plank_pose()] * 20):
        status = analyzer.update(frame, i * 100, 1.0)
    assert status is not None and status.rep_elapsed_ms == 1900


def test_a_brief_tracking_dropout_does_not_end_the_hold() -> None:
    plank = [plank_pose()] * 40
    analyzer = run_frames([STANDING] * 3 + plank + [None] * 5 + plank + [STANDING] * 3)
    assert len(analyzer.results) == 1


def test_a_long_tracking_dropout_discards_the_hold() -> None:
    plank = [plank_pose()] * 20
    analyzer = run_frames([STANDING] * 3 + plank + [None] * 20 + plank + [STANDING] * 3)
    assert analyzer.results == ()