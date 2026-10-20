from __future__ import annotations

from pose_tracker.config import AppConfig
from pose_tracker.domain.body_side import BodySide
from pose_tracker.domain.exercises.catalog import build_catalog
from pose_tracker.domain.pose import LandmarkId
from pose_tracker.domain.rule_joints import highlighted_landmarks


def test_every_rule_in_the_catalog_highlights_something() -> None:
    config = AppConfig()
    catalog = build_catalog(config.squat, config.shoulder_press, config.push_up, config.deadlift)
    for exercise in catalog.values():
        for rule in exercise.rules:
            assert highlighted_landmarks(rule.rule_id, BodySide.LEFT), (exercise.key, rule.rule_id)


def test_each_side_maps_to_its_own_landmarks() -> None:
    assert highlighted_landmarks("squat_depth", BodySide.LEFT) == (
        LandmarkId.LEFT_HIP, LandmarkId.LEFT_KNEE, LandmarkId.LEFT_ANKLE,
    )
    assert highlighted_landmarks("squat_depth", BodySide.RIGHT) == (
        LandmarkId.RIGHT_HIP, LandmarkId.RIGHT_KNEE, LandmarkId.RIGHT_ANKLE,
    )


def test_head_position_includes_the_ear_of_the_chosen_side() -> None:
    assert highlighted_landmarks("head_position", BodySide.RIGHT) == (
        LandmarkId.RIGHT_EAR, LandmarkId.RIGHT_SHOULDER, LandmarkId.RIGHT_HIP,
    )


def test_unknown_rule_highlights_nothing() -> None:
    assert highlighted_landmarks("made_up", BodySide.LEFT) == ()

def test_two_sided_rules_highlight_both_sides() -> None:
    assert highlighted_landmarks("elbow_bend", BodySide.LEFT) == (
        LandmarkId.LEFT_SHOULDER, LandmarkId.LEFT_ELBOW, LandmarkId.LEFT_WRIST,
        LandmarkId.RIGHT_SHOULDER, LandmarkId.RIGHT_ELBOW, LandmarkId.RIGHT_WRIST,
    )