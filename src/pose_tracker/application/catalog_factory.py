from __future__ import annotations

import dataclasses
from collections.abc import Collection, Mapping

from pose_tracker.config import AppConfig
from pose_tracker.domain.exercise import Exercise
from pose_tracker.domain.exercises.catalog import build_catalog

# AppConfig field (the section name in calibration.toml) -> exercise key.
SECTION_EXERCISES: Mapping[str, str] = {
    "squat": "squat",
    "shoulder_press": "shoulder_press",
    "push_up": "push_up",
    "deadlift": "deadlift",
    "curl": "bicep_curl",
    "bench_press": "bench_press",
    "lateral_raise": "lateral_raise",
    "plank": "plank",
    "incline_press": "incline_press",
    "decline_press": "decline_press",
    "pulldown_wide": "lat_pulldown_wide",
    "pulldown_close": "lat_pulldown_close",
    "hip_thrust": "hip_thrust",
    "bent_over_row": "bent_over_row",
    "calf_raise": "calf_raise",
}


def catalog_for(
    config: AppConfig, disabled_rules: Mapping[str, Collection[str]] | None = None
) -> dict[str, Exercise]:
    """Every exercise, built from the thresholds in the app configuration.

    ``disabled_rules`` maps a section name to rule ids that are switched off for that exercise.
    """
    catalog = build_catalog(
        config.squat, config.shoulder_press, config.push_up, config.deadlift, config.curl,
        config.bench_press, config.lateral_raise, config.plank,
        incline_press=config.incline_press, decline_press=config.decline_press,
        pulldown_wide=config.pulldown_wide, pulldown_close=config.pulldown_close,
        hip_thrust=config.hip_thrust, bent_over_row=config.bent_over_row,
        calf_raise=config.calf_raise,
    )
    for section, rule_ids in (disabled_rules or {}).items():
        key = SECTION_EXERCISES[section]
        off = set(rule_ids)
        catalog[key] = dataclasses.replace(
            catalog[key], rules=tuple(r for r in catalog[key].rules if r.rule_id not in off)
        )
    return catalog