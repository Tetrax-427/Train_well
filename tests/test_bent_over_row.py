from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pose_factory import deadlift_pose

from pose_tracker.application.exercise_analyzer import ExerciseAnalyzer
from pose_tracker.domain.exercises.bent_over_row import BentOverRowSettings, build_bent_over_row
from pose_tracker.domain.view import StableViewDetector, ViewDetector

# Path and steadiness are covered in test_motion_rules; these coarse steps would trip them.
RELAXED = BentOverRowSettings(max_path_deviation=10.0, max_unsteadiness=10.0)

GOOD = [175] * 6 + list(range(170, 74, -5)) + list(range(80, 176, 5))        # down to 75 degrees
SHALLOW = [175] * 6 + list(range(170, 109, -5)) + list(range(115, 176, 5))   # only down to 110
NO_STRETCH = [152] * 6 + list(range(148, 74, -5)) + list(range(80, 156, 5))  # arms never straighten

def run(
    elbows: list[int],
    torso: Callable[[int], float] = lambda _elbow: 50.0,
    chord: Callable[[int], float] = lambda _elbow: 0.0,
    **pose_kwargs: Any,
) -> ExerciseAnalyzer:
    analyzer = ExerciseAnalyzer(
        build_bent_over_row(RELAXED), StableViewDetector(ViewDetector(), frames_to_switch=1)
    )
    for i, elbow in enumerate(elbows):
        pose = deadlift_pose(
            130, torso_deg=torso(elbow), elbow_angle_deg=elbow, chord_shrink=chord(elbow),
            **pose_kwargs,
        )
        analyzer.update(pose, i * 100, 1.0)
    return analyzer


def violations(analyzer: ExerciseAnalyzer) -> list[str]:
    assert len(analyzer.results) == 1
    return [v.rule_id for v in analyzer.results[0].violations]


def test_clean_row() -> None:
    analyzer = run(GOOD)
    assert len(analyzer.results) == 1
    assert analyzer.results[0].is_clean


def test_not_pulling_high_enough() -> None:
    assert violations(run(SHALLOW)) == ["row_top"]


def test_not_straightening_the_arms() -> None:
    assert violations(run(NO_STRETCH)) == ["row_stretch"]


def test_standing_too_upright() -> None:
    assert violations(run(GOOD, torso=lambda _elbow: 15.0)) == ["row_hinge"]


def test_heaving_the_torso_up() -> None:
    heave: Callable[[int], float] = lambda elbow: 50.0 if elbow > 135 else 20.0  # noqa: E731
    assert violations(run(GOOD, torso=heave)) == ["torso_swing"]


def test_rounding_the_back_during_the_pull() -> None:
    round_back: Callable[[int], float] = lambda elbow: 0.15 if elbow <= 135 else 0.0  # noqa: E731
    assert violations(run(GOOD, chord=round_back)) == ["back_rounding"]


def test_head_out_of_line() -> None:
    assert violations(run(GOOD, neck_angle_deg=120)) == ["head_position"]