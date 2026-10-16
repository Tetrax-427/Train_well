from __future__ import annotations

from collections.abc import Callable

from pose_factory import curl_pose

from pose_tracker.application.exercise_analyzer import ExerciseAnalyzer
from pose_tracker.domain.exercises.curl import CurlSettings, build_curl
from pose_tracker.domain.view import StableViewDetector, ViewDetector

# Steadiness is covered in test_motion_rules; these coarse synthetic steps would trip it.
RELAXED = CurlSettings(max_unsteadiness=10.0)

GOOD = [170] * 6 + list(range(160, 39, -10)) + list(range(50, 171, 10))     # up to 40 degrees
SHORT_TOP = [170] * 6 + list(range(160, 79, -10)) + list(range(90, 171, 10))  # only to 80
HALF_LOWER = [150] * 6 + list(range(140, 39, -10)) + list(range(50, 151, 10))  # never straightens


def run(
    elbows: list[int],
    upper_arm: float = 5.0,
    layback: Callable[[int], float] = lambda _frame: 0.0,
    facing: int = 1,
) -> ExerciseAnalyzer:
    analyzer = ExerciseAnalyzer(
        build_curl(RELAXED), StableViewDetector(ViewDetector(), frames_to_switch=1)
    )
    for i, elbow in enumerate(elbows):
        analyzer.update(curl_pose(elbow, upper_arm, layback(i), facing), i * 100, 1.0)
    return analyzer


def violations(analyzer: ExerciseAnalyzer) -> list[str]:
    assert len(analyzer.results) == 1
    return [v.rule_id for v in analyzer.results[0].violations]


def test_good_curl_is_one_clean_rep() -> None:
    analyzer = run(GOOD)
    assert len(analyzer.results) == 1
    assert analyzer.results[0].is_clean


def test_facing_the_other_way_gives_the_same_result() -> None:
    assert run(GOOD, facing=-1).results[0].is_clean


def test_stopping_short_at_the_top() -> None:
    assert violations(run(SHORT_TOP)) == ["curl_top"]


def test_not_lowering_all_the_way() -> None:
    assert violations(run(HALF_LOWER)) == ["curl_bottom"]


def test_elbow_swinging_away_from_the_body() -> None:
    assert violations(run(GOOD, upper_arm=45)) == ["elbow_drift"]


def test_swinging_the_torso() -> None:
    swing = lambda frame: 15.0 if frame % 2 else 0.0  # noqa: E731
    assert violations(run(GOOD, layback=swing)) == ["torso_swing"]