from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from pose_factory import bench_pose, press_pose

from pose_tracker.application.exercise_analyzer import ExerciseAnalyzer
from pose_tracker.domain.exercises.bench_press import BenchPressSettings, build_bench_press
from pose_tracker.domain.view import StableViewDetector, ViewDetector

# Steadiness is covered in test_motion_rules; these coarse synthetic steps would trip it.
RELAXED = BenchPressSettings(max_unsteadiness=10.0)

GOOD = [175] * 6 + list(range(170, 75, -5)) + list(range(80, 176, 5))      # down to 80 degrees
SHALLOW = [175] * 6 + list(range(170, 100, -5)) + list(range(105, 176, 5))  # only down to 105
NO_LOCKOUT = [157] * 6 + list(range(150, 75, -5)) + list(range(80, 156, 5))  # never past 157


def make_analyzer(settings: BenchPressSettings) -> ExerciseAnalyzer:
    return ExerciseAnalyzer(
        build_bench_press(settings), StableViewDetector(ViewDetector(), frames_to_switch=1)
    )


def run(
    elbows: list[int],
    settings: BenchPressSettings = RELAXED,
    arm_tilt: Callable[[int], float] = lambda _elbow: 0.0,
    **pose_kwargs: Any,
) -> ExerciseAnalyzer:
    analyzer = make_analyzer(settings)
    for i, elbow in enumerate(elbows):
        analyzer.update(
            bench_pose(elbow, arm_tilt_deg=arm_tilt(elbow), **pose_kwargs), i * 100, 1.0
        )
    return analyzer


def violations(analyzer: ExerciseAnalyzer) -> list[str]:
    assert len(analyzer.results) == 1
    return [v.rule_id for v in analyzer.results[0].violations]


def test_good_press_is_one_clean_rep() -> None:
    analyzer = run(GOOD)
    assert len(analyzer.results) == 1
    assert analyzer.results[0].is_clean


def test_facing_the_other_way_gives_the_same_result() -> None:
    assert run(GOOD, direction=-1).results[0].is_clean


def test_not_lowering_enough() -> None:
    assert violations(run(SHALLOW)) == ["bench_depth"]


def test_not_locking_out() -> None:
    assert violations(run(NO_LOCKOUT)) == ["bench_lockout"]


def test_hips_lifting() -> None:
    assert violations(run(GOOD, tilt_deg=20)) == ["hips_lifted"]


def test_over_arching() -> None:
    assert violations(run(GOOD, tilt_deg=-20)) == ["back_arch"]


def test_head_lifted_off_the_bench() -> None:
    assert violations(run(GOOD, neck_angle_deg=120)) == ["head_position"]


def test_bowed_press_path() -> None:
    settings = BenchPressSettings(max_unsteadiness=10.0, max_hand_drift=1.0)
    bow: Callable[[int], float] = lambda elbow: 30.0 * math.sin(math.pi * (175 - elbow) / 95)  # noqa: E731
    assert violations(run(GOOD, settings, arm_tilt=bow)) == ["bar_path"]


def test_pressing_forward_instead_of_straight_up() -> None:
    settings = BenchPressSettings(max_unsteadiness=10.0, max_hand_drift=0.1)
    tilted: Callable[[int], float] = lambda _elbow: 45.0  # noqa: E731
    assert violations(run(GOOD, settings, arm_tilt=tilted)) == ["bar_drift"]


def test_standing_up_is_not_counted_as_a_bench_press() -> None:
    analyzer = make_analyzer(RELAXED)
    for i, elbow in enumerate(GOOD):
        analyzer.update(press_pose(elbow), i * 100, 1.0)
    assert analyzer.results == ()