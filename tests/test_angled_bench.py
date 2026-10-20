from __future__ import annotations

import dataclasses
from collections.abc import Callable
from typing import Any

from pose_factory import bench_pose

from pose_tracker.application.exercise_analyzer import ExerciseAnalyzer
from pose_tracker.domain.exercise import Exercise
from pose_tracker.domain.exercises.angled_bench import (
    DECLINE,
    INCLINE,
    build_decline_press,
    build_incline_press,
)
from pose_tracker.domain.view import StableViewDetector, ViewDetector

# Steadiness is covered in test_motion_rules; these coarse synthetic steps would trip it.
INCLINE_PRESS = build_incline_press(dataclasses.replace(INCLINE, max_unsteadiness=10.0))
DECLINE_PRESS = build_decline_press(dataclasses.replace(DECLINE, max_unsteadiness=10.0))
SLIDING_BACK = build_incline_press(dataclasses.replace(
    INCLINE, max_unsteadiness=10.0, max_path_deviation=10.0, max_hand_drift=10.0
))

GOOD = [175] * 6 + list(range(170, 75, -5)) + list(range(80, 176, 5))
SHALLOW = [175] * 6 + list(range(170, 100, -5)) + list(range(105, 176, 5))
NO_LOCKOUT = [157] * 6 + list(range(150, 75, -5)) + list(range(80, 156, 5))


def run(
    exercise: Exercise, elbows: list[int], tilt: Callable[[int], float], **pose_kwargs: Any
) -> ExerciseAnalyzer:
    analyzer = ExerciseAnalyzer(
        exercise, StableViewDetector(ViewDetector(), frames_to_switch=1)
    )
    for i, elbow in enumerate(elbows):
        analyzer.update(bench_pose(elbow, tilt_deg=tilt(i), **pose_kwargs), i * 100, 1.0)
    return analyzer


def violations(analyzer: ExerciseAnalyzer) -> list[str]:
    assert len(analyzer.results) == 1
    return [v.rule_id for v in analyzer.results[0].violations]


def test_clean_incline_press() -> None:
    analyzer = run(INCLINE_PRESS, GOOD, lambda _i: -35.0)
    assert len(analyzer.results) == 1
    assert analyzer.results[0].is_clean


def test_clean_decline_press() -> None:
    analyzer = run(DECLINE_PRESS, GOOD, lambda _i: 20.0)
    assert len(analyzer.results) == 1
    assert analyzer.results[0].is_clean


def test_a_flat_bench_posture_is_not_an_incline_or_decline_press() -> None:
    assert run(INCLINE_PRESS, GOOD, lambda _i: 0.0).results == ()
    assert run(DECLINE_PRESS, GOOD, lambda _i: 0.0).results == ()


def test_each_press_only_counts_its_own_angle() -> None:
    assert run(DECLINE_PRESS, GOOD, lambda _i: -35.0).results == ()
    assert run(INCLINE_PRESS, GOOD, lambda _i: 20.0).results == ()


def test_not_lowering_enough() -> None:
    assert violations(run(INCLINE_PRESS, SHALLOW, lambda _i: -35.0)) == ["bench_depth"]


def test_not_locking_out() -> None:
    assert violations(run(DECLINE_PRESS, NO_LOCKOUT, lambda _i: 20.0)) == ["bench_lockout"]


def test_back_sliding_on_the_bench() -> None:
    sliding: Callable[[int], float] = lambda i: -35.0 if i % 2 else -55.0  # noqa: E731
    assert violations(run(SLIDING_BACK, GOOD, sliding)) == ["bench_angle"]


def test_head_lifted_off_the_bench() -> None:
    result = run(INCLINE_PRESS, GOOD, lambda _i: -35.0, neck_angle_deg=120)
    assert violations(result) == ["head_position"]