from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pose_factory import calf_pose

from pose_tracker.application.exercise_analyzer import ExerciseAnalyzer
from pose_tracker.domain.exercises.calf_raise import CalfRaiseSettings, build_calf_raise
from pose_tracker.domain.view import StableViewDetector, ViewDetector

NO_TEMPO = CalfRaiseSettings(min_rep_seconds=0.0)  # the coarse synthetic steps are fast

GOOD = [2] * 6 + [6, 10, 14, 18, 22, 26, 30, 26, 22, 18, 14, 10, 6, 2]            # up to 30 degrees
LOW = [2] * 6 + [6, 10, 14, 16, 17, 16, 12, 10, 8, 4, 2]                          # only up to 17
FAST = [2] * 6 + [10, 20, 30, 20, 10, 2]  # a 0.4 s rep

def run(
    angles: list[int],
    settings: CalfRaiseSettings = NO_TEMPO,
    lean: Callable[[int], float] = lambda _i: 0.0,
    **pose_kwargs: Any,
) -> ExerciseAnalyzer:
    analyzer = ExerciseAnalyzer(
        build_calf_raise(settings), StableViewDetector(ViewDetector(), frames_to_switch=1)
    )
    for i, angle in enumerate(angles):
        analyzer.update(calf_pose(angle, lean_deg=lean(i), **pose_kwargs), i * 100, 1.0)
    return analyzer


def violations(analyzer: ExerciseAnalyzer) -> list[str]:
    assert len(analyzer.results) == 1
    return [v.rule_id for v in analyzer.results[0].violations]


def test_clean_calf_raise() -> None:
    analyzer = run(GOOD)
    assert len(analyzer.results) == 1
    assert analyzer.results[0].is_clean


def test_facing_the_other_way_gives_the_same_result() -> None:
    assert run(GOOD, facing=-1).results[0].is_clean


def test_not_rising_high_enough() -> None:
    assert violations(run(LOW)) == ["calf_height"]


def test_bending_the_knees() -> None:
    assert violations(run(GOOD, knee_angle_deg=150.0)) == ["knee_bend"]


def test_swaying_the_torso() -> None:
    sway: Callable[[int], float] = lambda i: 12.0 if i % 2 else 0.0  # noqa: E731
    assert violations(run(GOOD, lean=sway)) == ["torso_swing"]


def test_bouncing_through_the_rep() -> None:
    assert violations(run(FAST, CalfRaiseSettings())) == ["calf_tempo"]

def test_standing_still_is_not_a_rep() -> None:
    assert run([2] * 30).results == ()