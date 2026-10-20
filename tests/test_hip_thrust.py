from __future__ import annotations

from typing import Any

from pose_factory import press_pose, thrust_pose

from pose_tracker.application.exercise_analyzer import ExerciseAnalyzer
from pose_tracker.domain.exercises.hip_thrust import HipThrustSettings, build_hip_thrust
from pose_tracker.domain.view import StableViewDetector, ViewDetector

NO_TEMPO = HipThrustSettings(min_rep_seconds=0.0)  # the coarse synthetic steps are fast

GOOD = [100] * 6 + [105, 115, 125, 135, 145, 155, 165, 175, 178, 175, 165, 155, 145, 135, 125, 115, 105, 100]
LOW_TOP = [100] * 6 + [105, 115, 125, 135, 145, 155, 160, 155, 145, 135, 125, 115, 105, 100]


def run(
    hips: list[int], settings: HipThrustSettings = NO_TEMPO, **pose_kwargs: Any
) -> ExerciseAnalyzer:
    analyzer = ExerciseAnalyzer(
        build_hip_thrust(settings), StableViewDetector(ViewDetector(), frames_to_switch=1)
    )
    for i, hip in enumerate(hips):
        analyzer.update(thrust_pose(hip, **pose_kwargs), i * 100, 1.0)
    return analyzer


def violations(analyzer: ExerciseAnalyzer) -> list[str]:
    assert len(analyzer.results) == 1
    return [v.rule_id for v in analyzer.results[0].violations]


def test_clean_hip_thrust() -> None:
    analyzer = run(GOOD)
    assert len(analyzer.results) == 1
    assert analyzer.results[0].is_clean


def test_hips_not_fully_extended() -> None:
    assert violations(run(LOW_TOP)) == ["thrust_lockout"]


def test_feet_in_the_wrong_place() -> None:
    assert violations(run(GOOD, shin_angle_deg=40.0)) == ["foot_placement"]


def test_head_out_of_line() -> None:
    assert violations(run(GOOD, neck_angle_deg=120.0)) == ["head_position"]


def test_bouncing_through_the_rep() -> None:
    assert violations(run(GOOD, HipThrustSettings())) == ["thrust_tempo"]


def test_standing_up_is_not_a_hip_thrust() -> None:
    analyzer = ExerciseAnalyzer(
        build_hip_thrust(NO_TEMPO), StableViewDetector(ViewDetector(), frames_to_switch=1)
    )
    for i in range(30):
        analyzer.update(press_pose(120), i * 100, 1.0)
    assert analyzer.results == ()