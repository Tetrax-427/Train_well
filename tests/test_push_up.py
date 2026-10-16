from __future__ import annotations

from typing import Any

from pose_factory import press_pose, pushup_pose

from pose_tracker.application.exercise_analyzer import ExerciseAnalyzer
from pose_tracker.domain.exercises.push_up import build_push_up
from pose_tracker.domain.view import StableViewDetector, ViewDetector

GOOD = [170] * 4 + list(range(165, 84, -5)) + list(range(90, 171, 5))
SHALLOW = [170] * 4 + list(range(165, 109, -5)) + list(range(115, 171, 5))
NO_LOCKOUT = [155] * 4 + list(range(150, 84, -5)) + list(range(90, 156, 5))


def make_analyzer() -> ExerciseAnalyzer:
    return ExerciseAnalyzer(
        build_push_up(), StableViewDetector(ViewDetector(), frames_to_switch=1)
    )


def run(elbows: list[int], **pose_kwargs: Any) -> ExerciseAnalyzer:
    analyzer = make_analyzer()
    for i, elbow in enumerate(elbows):
        analyzer.update(pushup_pose(elbow, **pose_kwargs), i * 100, 1.0)
    return analyzer


def violations(analyzer: ExerciseAnalyzer) -> list[str]:
    assert len(analyzer.results) == 1
    return [v.rule_id for v in analyzer.results[0].violations]


def test_good_pushup_is_one_clean_rep() -> None:
    analyzer = run(GOOD)
    assert len(analyzer.results) == 1
    assert analyzer.results[0].is_clean


def test_shallow_pushup_is_flagged() -> None:
    assert violations(run(SHALLOW)) == ["pushup_depth"]


def test_incomplete_lockout_is_flagged() -> None:
    assert violations(run(NO_LOCKOUT)) == ["pushup_lockout"]


def test_sagging_hips_are_flagged() -> None:
    assert violations(run(GOOD, hip_sag_deg=25)) == ["hip_sag"]


def test_piking_hips_are_flagged() -> None:
    assert violations(run(GOOD, hip_sag_deg=-25)) == ["hip_pike"]


def test_bent_knees_are_flagged() -> None:
    assert "knee_bend" in violations(run(GOOD, knee_angle_deg=130))


def test_dropped_head_is_flagged() -> None:
    assert violations(run(GOOD, neck_angle_deg=120)) == ["head_position"]


def test_hands_too_far_forward_are_flagged() -> None:
    assert violations(run(GOOD, hand_ahead=0.5)) == ["hand_placement"]


def test_facing_the_other_way_gives_the_same_result() -> None:
    assert run(GOOD, facing=-1).results[0].is_clean


def test_upright_body_is_not_counted_as_a_pushup() -> None:
    analyzer = make_analyzer()
    for i, elbow in enumerate(GOOD):
        analyzer.update(press_pose(elbow), i * 100, 1.0)
    assert analyzer.results == ()