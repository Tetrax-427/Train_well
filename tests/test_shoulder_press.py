from __future__ import annotations

from pose_factory import press_pose

from pose_tracker.application.exercise_analyzer import ExerciseAnalyzer
from pose_tracker.domain.exercises.shoulder_press import (
    ShoulderPressSettings,
    build_shoulder_press,
)
from pose_tracker.domain.view import StableViewDetector, ViewDetector

# Path and steadiness are covered in test_motion_rules. They are relaxed here so these
# tests isolate depth, lockout and lean on perfectly synthetic motion.
RELAXED = ShoulderPressSettings(max_path_deviation=1.0, max_unsteadiness=1.0)

GOOD = [90] * 5 + list(range(95, 176, 5)) + list(range(170, 89, -5))
SHALLOW = [120] * 5 + list(range(125, 176, 5)) + list(range(170, 119, -5))
NO_LOCKOUT = [90] * 5 + list(range(95, 151, 5)) + list(range(145, 89, -5))


def run(elbows: list[int], layback: float = 0.0, facing: int = 1) -> ExerciseAnalyzer:
    analyzer = ExerciseAnalyzer(
        build_shoulder_press(RELAXED),
        StableViewDetector(ViewDetector(), frames_to_switch=1),
    )
    for i, elbow in enumerate(elbows):
        analyzer.update(press_pose(elbow, layback, facing), i * 100, 1.0)
    return analyzer


def violations(analyzer: ExerciseAnalyzer) -> list[str]:
    return [v.rule_id for v in analyzer.results[0].violations]


def test_good_press_is_one_clean_rep() -> None:
    analyzer = run(GOOD)
    assert len(analyzer.results) == 1
    assert analyzer.results[0].is_clean


def test_not_lowering_enough_is_flagged() -> None:
    assert violations(run(SHALLOW)) == ["press_bottom"]


def test_incomplete_lockout_is_flagged() -> None:
    assert violations(run(NO_LOCKOUT)) == ["press_lockout"]


def test_leaning_back_is_flagged_whichever_way_you_face() -> None:
    assert violations(run(GOOD, layback=25, facing=1)) == ["layback"]
    assert violations(run(GOOD, layback=25, facing=-1)) == ["layback"]