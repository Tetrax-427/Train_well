from __future__ import annotations

from typing import Any

from pose_factory import deadlift_pose

from pose_tracker.application.exercise_analyzer import ExerciseAnalyzer
from pose_tracker.domain.exercises.deadlift import DeadliftSettings, build_deadlift
from pose_tracker.domain.view import StableViewDetector, ViewDetector

# Steadiness is covered in test_motion_rules; these coarse synthetic steps would trip it.
RELAXED = DeadliftSettings(max_unsteadiness=10.0)
REST_ANGLE = RELAXED.rest_hip_angle

CLEAN = [90] * 8 + [130, 150, 165, 175, 165, 150, 130, 105]
LOW_TOP = [90] * 8 + [130, 150, 160, 150, 130, 105]


def clean_params(hip: float) -> dict[str, Any]:
    return {
        "torso_deg": (180 - hip) / 2,
        "knee_angle_deg": min(180.0, 120 + (hip - 90) * 0.7),
    }


def run(
    hips: list[int],
    rest: dict[str, Any] | None = None,
    pull: dict[str, Any] | None = None,
    facing: int = 1,
) -> ExerciseAnalyzer:
    """``rest`` overrides apply in the bottom position, ``pull`` overrides everywhere else."""
    analyzer = ExerciseAnalyzer(
        build_deadlift(RELAXED), StableViewDetector(ViewDetector(), frames_to_switch=1)
    )
    for i, hip in enumerate(hips):
        params = clean_params(hip)
        params.update((rest if hip <= REST_ANGLE else pull) or {})
        analyzer.update(deadlift_pose(hip, facing=facing, **params), i * 100, 1.0)
    return analyzer


def violations(analyzer: ExerciseAnalyzer) -> list[str]:
    assert len(analyzer.results) == 1
    return [v.rule_id for v in analyzer.results[0].violations]


def test_clean_deadlift_is_one_clean_rep() -> None:
    analyzer = run(CLEAN)
    assert len(analyzer.results) == 1
    assert analyzer.results[0].is_clean


def test_facing_the_other_way_gives_the_same_result() -> None:
    assert run(CLEAN, facing=-1).results[0].is_clean


def test_back_too_bent_at_the_start() -> None:
    assert violations(run(CLEAN, rest={"torso_deg": 80})) == ["start_back"]


def test_hips_shooting_up() -> None:
    assert violations(run(CLEAN, pull={"torso_deg": 60})) == ["hips_shoot_up"]


def test_back_rounding_shows_as_a_shrinking_chord() -> None:
    assert violations(run(CLEAN, pull={"chord_shrink": 0.15})) == ["back_rounding"]


def test_leaning_back_at_the_top() -> None:
    assert violations(run(CLEAN, pull={"torso_deg": -12})) == ["lockout_arch"]


def test_head_out_of_line() -> None:
    assert violations(run(CLEAN, pull={"neck_angle_deg": 130})) == ["head_position"]


def test_incomplete_hip_extension() -> None:
    assert violations(run(LOW_TOP, pull={"knee_angle_deg": 180.0})) == ["hip_extension"]


def test_knees_not_locked_out() -> None:
    assert violations(run(CLEAN, pull={"knee_angle_deg": 150})) == ["knee_lockout"]


def test_bent_arms() -> None:
    assert violations(run(CLEAN, pull={"elbow_angle_deg": 140})) == ["arms_straight"]


def test_bar_not_over_mid_foot_at_the_start() -> None:
    assert violations(run(CLEAN, rest={"bar_offset": -0.3})) == ["bar_start"]


def test_bar_drifting_forward() -> None:
    assert violations(run(CLEAN, pull={"bar_offset": 0.4})) == ["bar_forward"]


def test_squatting_the_lift() -> None:
    assert violations(run(CLEAN, rest={"knee_angle_deg": 80})) == ["start_knees"]