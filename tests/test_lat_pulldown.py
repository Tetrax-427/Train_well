from __future__ import annotations

import dataclasses
from collections.abc import Callable
from typing import Any

from pose_factory import pulldown_pose

from pose_tracker.application.exercise_analyzer import ExerciseAnalyzer
from pose_tracker.domain.exercise import Exercise
from pose_tracker.domain.exercises.lat_pulldown import (
    CLOSE_GRIP,
    WIDE_GRIP,
    build_close_pulldown,
    build_wide_pulldown,
)
from pose_tracker.domain.view import StableViewDetector, ViewDetector

# Steadiness is covered in test_motion_rules; these coarse synthetic steps would trip it.
# Grip is relaxed except in the grip tests, and the stretch is relaxed whenever the wrists are
# moved by hand (which changes the elbow angles).
RELAXED = dataclasses.replace(
    WIDE_GRIP, min_grip_ratio=0.0, max_grip_ratio=100.0, max_unsteadiness=10.0
)
WIDE_GRIP_TEST = dataclasses.replace(WIDE_GRIP, min_stretch_deg=0.0, max_unsteadiness=10.0)
CLOSE_GRIP_TEST = dataclasses.replace(CLOSE_GRIP, min_stretch_deg=0.0, max_unsteadiness=10.0)

GOOD = [150] * 6 + list(range(145, 49, -5)) + list(range(55, 151, 5))   # down to 50 degrees
SHALLOW = [150] * 6 + list(range(145, 79, -5)) + list(range(85, 151, 5))  # only down to 80


def straightening(elevation: int) -> float:
    """Arms straighten as they go up: 175 degrees at the top, 75 at the bottom."""
    return float(min(175, max(60, elevation + 25)))


def run(
    exercise: Exercise,
    elevations: list[int],
    elbow: Callable[[int], float] = straightening,
    **pose_kwargs: Any,
) -> ExerciseAnalyzer:
    analyzer = ExerciseAnalyzer(
        exercise, StableViewDetector(ViewDetector(), frames_to_switch=1)
    )
    for i, elevation in enumerate(elevations):
        analyzer.update(pulldown_pose(elevation, elbow(elevation), **pose_kwargs), i * 100, 1.0)
    return analyzer


def violations(analyzer: ExerciseAnalyzer) -> list[str]:
    assert len(analyzer.results) == 1
    return [v.rule_id for v in analyzer.results[0].violations]


def test_clean_pulldown() -> None:
    analyzer = run(build_wide_pulldown(RELAXED), GOOD)
    assert len(analyzer.results) == 1
    assert analyzer.results[0].is_clean


def test_not_pulling_down_far_enough() -> None:
    assert violations(run(build_wide_pulldown(RELAXED), SHALLOW)) == ["pulldown_depth"]


def test_arms_not_straightening_at_the_top() -> None:
    result = run(build_wide_pulldown(RELAXED), GOOD, elbow=lambda _e: 140.0)
    assert violations(result) == ["pulldown_stretch"]


def test_uneven_bar() -> None:
    relaxed_stretch = dataclasses.replace(RELAXED, min_stretch_deg=0.0)
    result = run(build_wide_pulldown(relaxed_stretch), GOOD, bar_tilt=0.1)
    assert violations(result) == ["bar_level"]


def test_wide_grip_needs_wide_hands() -> None:
    exercise = build_wide_pulldown(WIDE_GRIP_TEST)
    assert run(exercise, GOOD, grip_ratio=2.2).results[0].is_clean
    assert violations(run(exercise, GOOD, grip_ratio=1.0)) == ["grip_width"]


def test_close_grip_needs_hands_close_together() -> None:
    exercise = build_close_pulldown(CLOSE_GRIP_TEST)
    assert run(exercise, GOOD, grip_ratio=0.8).results[0].is_clean
    assert violations(run(exercise, GOOD, grip_ratio=2.2)) == ["grip_width"]


def test_the_two_variants_are_separate_exercises() -> None:
    assert build_wide_pulldown().key != build_close_pulldown().key