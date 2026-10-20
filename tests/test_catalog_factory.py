from __future__ import annotations

from pose_tracker.application.calibration import sections
from pose_tracker.application.catalog_factory import SECTION_EXERCISES, catalog_for
from pose_tracker.config import AppConfig


def test_every_exercise_has_exactly_one_calibration_section() -> None:
    base = AppConfig()
    assert set(SECTION_EXERCISES.values()) == set(catalog_for(base))
    assert len(set(SECTION_EXERCISES.values())) == len(SECTION_EXERCISES)
    assert set(SECTION_EXERCISES) <= set(sections(base))


def test_the_only_other_sections_are_the_general_ones() -> None:
    assert set(sections(AppConfig())) - set(SECTION_EXERCISES) == {"view_thresholds", "smoothing"}


def test_disabling_rules_leaves_other_exercises_and_the_order_alone() -> None:
    base = AppConfig()
    normal = catalog_for(base)
    trimmed = catalog_for(base, {"squat": ["torso_lean"], "curl": ["control", "elbow_drift"]})

    assert list(trimmed) == list(normal)
    assert [r.rule_id for r in trimmed["squat"].rules] == ["squat_depth"]
    assert {"control", "elbow_drift"}.isdisjoint(r.rule_id for r in trimmed["bicep_curl"].rules)
    assert [r.rule_id for r in trimmed["deadlift"].rules] == [
        r.rule_id for r in normal["deadlift"].rules
    ]