from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pose_factory import front_pose

from pose_tracker.application.exercise_analyzer import ExerciseAnalyzer
from pose_tracker.domain.exercises.lateral_raise import LateralRaiseSettings, build_lateral_raise
from pose_tracker.domain.view import StableViewDetector, ViewDetector

# Steadiness is covered in test_motion_rules; these coarse synthetic steps would trip it.
RELAXED = LateralRaiseSettings(max_unsteadiness=10.0)

GOOD = [10] * 6 + list(range(15, 91, 5)) + list(range(85, 9, -5))        # up to 90 degrees
LOW = [10] * 6 + list(range(15, 61, 5)) + list(range(55, 9, -5))         # only up to 60
HIGH = [10] * 6 + list(range(15, 121, 5)) + list(range(115, 9, -5))      # up to 120
LEFT_HIGH = [10] * 6 + list(range(15, 101, 5)) + list(range(95, 9, -5))  # left arm up to 100

PoseArgs = Callable[[int, int], dict[str, Any]]  # (frame index, left raise) -> front_pose kwargs


def run(
    raises: list[int],
    pose_args: PoseArgs = lambda _i, _raised: {},
    right: Callable[[int], int] | None = None,
) -> ExerciseAnalyzer:
    analyzer = ExerciseAnalyzer(
        build_lateral_raise(RELAXED), StableViewDetector(ViewDetector(), frames_to_switch=1)
    )
    for i, raised in enumerate(raises):
        other = None if right is None else right(raised)
        analyzer.update(front_pose(raised, other, **pose_args(i, raised)), i * 100, 1.0)
    return analyzer


def violations(analyzer: ExerciseAnalyzer) -> list[str]:
    assert len(analyzer.results) == 1
    return [v.rule_id for v in analyzer.results[0].violations]


def test_good_set_is_one_clean_rep() -> None:
    analyzer = run(GOOD)
    assert len(analyzer.results) == 1
    assert analyzer.results[0].is_clean


def test_not_raising_high_enough() -> None:
    assert violations(run(LOW)) == ["raise_height"]


def test_lifting_above_shoulder_height() -> None:
    assert violations(run(HIGH)) == ["raise_too_high"]


def test_uneven_arms() -> None:
    assert violations(run(LEFT_HIGH, right=lambda raised: min(raised, 70))) == ["arm_symmetry"]


def test_bent_elbows() -> None:
    assert violations(run(GOOD, lambda _i, _raised: {"elbow_angle_deg": 100})) == ["elbow_bend"]


def test_shrugging() -> None:
    shrug: PoseArgs = lambda _i, raised: {"shrug": 0.3 if raised > 30 else 0.0}  # noqa: E731
    assert violations(run(GOOD, shrug)) == ["shrugging"]


def test_swaying_the_body() -> None:
    sway: PoseArgs = lambda i, _raised: {"sway_deg": 10.0 if i % 2 else -10.0}  # noqa: E731
    assert violations(run(GOOD, sway)) == ["body_sway"]