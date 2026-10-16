from __future__ import annotations

from pose_tracker.config import AppConfig
from pose_tracker.domain.exercises.catalog import build_catalog


def test_every_rule_has_an_explanation_and_none_are_orphaned() -> None:
    config = AppConfig()
    catalog = build_catalog(config.squat, config.shoulder_press, config.push_up, config.deadlift)
    for exercise in catalog.values():
        rule_ids = {rule.rule_id for rule in exercise.rules}
        assert set(exercise.explanations) == rule_ids, exercise.key
        assert all(text.strip() for text in exercise.explanations.values()), exercise.key