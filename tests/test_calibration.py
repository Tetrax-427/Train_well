from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

import pytest

from pose_tracker.application.calibration import (
    DISABLED_RULES,
    calibrate,
    changed_settings,
    ordered_sections,
    render_effective,
    render_template,
    sections,
    summarize,
)
from pose_tracker.application.catalog_factory import catalog_for
from pose_tracker.config import AppConfig
from pose_tracker.errors import CalibrationError

BASE = AppConfig()


def problems(data: dict[str, Any]) -> str:
    with pytest.raises(CalibrationError) as info:
        calibrate(BASE, data)
    return str(info.value)


def rule(catalog: dict[str, Any], key: str, rule_id: str) -> Any:
    return next(r for r in catalog[key].rules if r.rule_id == rule_id)


def test_no_data_changes_nothing() -> None:
    calibration = calibrate(BASE, {})
    assert calibration.config == BASE
    assert changed_settings(BASE, calibration.config) == []
    assert summarize(BASE, calibration) == "0 setting(s) changed, 0 check(s) switched off"


def test_a_setting_reaches_the_exercise_rules() -> None:
    calibration = calibrate(BASE, {"squat": {"target_knee_angle": 110}})
    assert calibration.config.squat.target_knee_angle == 110.0
    assert isinstance(calibration.config.squat.target_knee_angle, float)
    assert rule(calibration.catalog, "squat", "squat_depth").target == 110.0
    assert calibration.config.deadlift == BASE.deadlift  # nothing else changes


def test_whole_number_settings_stay_integers() -> None:
    calibration = calibrate(BASE, {"curl": {"lead_in_ms": 2000}})
    assert calibration.config.curl.lead_in_ms == 2000
    assert isinstance(calibration.config.curl.lead_in_ms, int)
    assert "whole number" in problems({"curl": {"lead_in_ms": 2000.5}})


def test_general_sections_can_be_calibrated_too() -> None:
    calibration = calibrate(BASE, {"view_thresholds": {"side_max_ratio": 0.4}})
    assert calibration.config.view_thresholds.side_max_ratio == 0.4
    assert "[view_thresholds]" in problems({"view_thresholds": {"front_min_ratio": 0.2}})


def test_wrong_types_are_rejected() -> None:
    assert "expected a number" in problems({"squat": {"target_knee_angle": "deep"}})
    assert "expected a number" in problems({"squat": {"target_knee_angle": True}})
    assert "expected a number" in problems({"squat": {"target_knee_angle": float("nan")}})


def test_typos_get_a_suggestion() -> None:
    assert "Did you mean 'squat'" in problems({"squatt": {}})
    assert "Did you mean 'target_knee_angle'" in problems({"squat": {"target_knee_angl": 1}})


def test_a_section_must_be_a_table() -> None:
    assert "must be a table" in problems({"squat": 5})


def test_all_problems_are_reported_together_with_the_file_name() -> None:
    with pytest.raises(CalibrationError) as info:
        calibrate(BASE, {"squatt": {}, "deadlift": {"nope": 1}}, Path("calibration.toml"))
    text = str(info.value)
    assert text.startswith("calibration.toml has 2 problems:")
    assert "squatt" in text and "nope" in text


def test_rep_limits_that_cross_over_are_rejected() -> None:
    assert "cross over" in problems({"squat": {"leave_knee_angle": 170.0}})
    assert "must differ" in problems({"squat": {"leave_knee_angle": 160.0}})
    calibrate(BASE, {"squat": {"rest_knee_angle": 165.0}})  # still on the right side
    calibrate(BASE, {"calf_raise": {"leave_foot_angle": 20.0}})  # rising exercise stays rising


def test_rules_can_be_switched_off() -> None:
    calibration = calibrate(BASE, {"squat": {DISABLED_RULES: ["torso_lean", "torso_lean"]}})
    assert calibration.disabled_rules == {"squat": ("torso_lean",)}
    assert [r.rule_id for r in calibration.catalog["squat"].rules] == ["squat_depth"]
    assert len(calibration.catalog["deadlift"].rules) == len(catalog_for(BASE)["deadlift"].rules)


def test_the_section_name_picks_the_exercise_even_when_the_key_differs() -> None:
    calibration = calibrate(BASE, {"curl": {DISABLED_RULES: ["control"]}})
    assert "control" not in [r.rule_id for r in calibration.catalog["bicep_curl"].rules]


def test_bad_rule_lists_are_rejected() -> None:
    text = problems({"squat": {DISABLED_RULES: ["nope"]}})
    assert "unknown rule 'nope'" in text and "squat_depth" in text
    assert "expected a list" in problems({"squat": {DISABLED_RULES: "control"}})
    assert "unknown setting" in problems({"view_thresholds": {DISABLED_RULES: []}})


def test_changed_settings_lists_default_and_new_value() -> None:
    calibration = calibrate(BASE, {"squat": {"target_knee_angle": 120.0}})
    assert changed_settings(BASE, calibration.config) == [("squat", "target_knee_angle", 100.0, 120.0)]


def test_sections_come_in_a_readable_order() -> None:
    order = ordered_sections(BASE)
    assert order[:2] == ["view_thresholds", "smoothing"] or set(order[:2]) == {"view_thresholds", "smoothing"}
    assert order.index("squat") < order.index("deadlift") < order.index("bench_press")
    assert set(order) == set(sections(BASE))


# -- template and display ------------------------------------------------------------------


def test_the_template_is_valid_toml_and_changes_nothing() -> None:
    parsed = tomllib.loads(render_template(BASE))
    assert set(parsed) == set(sections(BASE))
    assert calibrate(BASE, parsed).config == BASE


def test_every_default_in_the_template_is_accepted_as_written() -> None:
    uncommented = [
        line[2:] if re.match(r"# \w+ = ", line) else line
        for line in render_template(BASE).splitlines()
    ]
    parsed = tomllib.loads("\n".join(uncommented))
    assert calibrate(BASE, parsed).config == BASE


def test_uncommenting_a_template_line_calibrates_it() -> None:
    text = render_template(BASE).replace("# target_knee_angle = 100.0", "target_knee_angle = 120.0")
    assert calibrate(BASE, tomllib.loads(text)).config.squat.target_knee_angle == 120.0


def test_the_template_lists_each_exercises_rules() -> None:
    assert "# Squat: rules are squat_depth, torso_lean" in render_template(BASE)


def test_effective_settings_mark_what_was_calibrated() -> None:
    calibration = calibrate(
        BASE, {"squat": {"target_knee_angle": 120.0, DISABLED_RULES: ["torso_lean"]}}
    )
    text = render_effective(BASE, calibration)
    marked = [line for line in text.splitlines() if "<- calibrated" in line]
    assert len(marked) == 1 and "target_knee_angle" in marked[0] and "(default 100.0)" in marked[0]
    assert '"torso_lean"' in text
    assert summarize(BASE, calibration) == "1 setting(s) changed, 1 check(s) switched off"


def test_a_single_section_can_be_shown() -> None:
    text = render_effective(BASE, calibrate(BASE, {}), only="squat")
    assert "[squat]" in text and "[deadlift]" not in text