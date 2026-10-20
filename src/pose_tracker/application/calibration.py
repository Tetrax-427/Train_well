from __future__ import annotations

import dataclasses
import difflib
import math
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pose_tracker.application.catalog_factory import SECTION_EXERCISES, catalog_for
from pose_tracker.config import AppConfig
from pose_tracker.domain.exercise import Exercise
from pose_tracker.errors import CalibrationError

DISABLED_RULES = "disabled_rules"

_HEADER = """\
# Pose Tracker calibration
#
# Every setting is listed with its default value, commented out.
# To calibrate: remove the leading '# ' from a line and change the value.
# To go back to the default: put the '# ' back (or delete the line).
#
# disabled_rules switches a form check off for that exercise; reps are still counted.
# Example:  disabled_rules = ["control"]
#
# After editing run:  python -m pose_tracker.calibrate check
# Restart the app to apply changes.
"""


@dataclass(frozen=True, slots=True, eq=False)
class Calibration:
    """The app configuration after applying calibration.toml, and the exercises built from it."""

    config: AppConfig
    catalog: dict[str, Exercise]
    disabled_rules: Mapping[str, tuple[str, ...]]  # section -> switched-off rule ids
    source: Path | None


def sections(config: AppConfig) -> dict[str, Any]:
    """Every AppConfig field that holds a settings object, by name: the calibration sections."""
    values = {f.name: getattr(config, f.name) for f in dataclasses.fields(config)}
    return {name: value for name, value in values.items() if dataclasses.is_dataclass(value)}


def ordered_sections(config: AppConfig) -> list[str]:
    """General sections first, then the exercises in routine order."""
    names = list(sections(config))
    routine = {key: index for index, key in enumerate(catalog_for(config))}
    exercises = sorted(
        (n for n in names if n in SECTION_EXERCISES), key=lambda n: routine[SECTION_EXERCISES[n]]
    )
    return [n for n in names if n not in SECTION_EXERCISES] + exercises


def calibrate(
    base: AppConfig, data: Mapping[str, Any], source: Path | None = None
) -> Calibration:
    """Apply calibration data (parsed TOML) on top of ``base``.

    Every problem found is reported together. Raises CalibrationError.
    """
    known = sections(base)
    base_catalog = catalog_for(base)
    problems: list[str] = []
    changes: dict[str, dict[str, Any]] = {}
    disabled: dict[str, tuple[str, ...]] = {}

    for name, table in data.items():
        if name not in known:
            problems.append(f"[{name}] is not a known section.{_suggest(name, known)}")
            continue
        if not isinstance(table, Mapping):
            problems.append(
                f"[{name}] must be a table: put '[{name}]' on its own line, then "
                "'setting = value' lines under it."
            )
            continue
        current = known[name]
        exercise_key = SECTION_EXERCISES.get(name)
        setting_names = {f.name for f in dataclasses.fields(current)}
        options = sorted(setting_names | ({DISABLED_RULES} if exercise_key else set()))
        for key, value in table.items():
            if key == DISABLED_RULES and exercise_key is not None:
                valid = {rule.rule_id for rule in base_catalog[exercise_key].rules}
                rule_ids, error = _check_rule_list(value, valid)
                if error is None:
                    disabled[name] = rule_ids
                else:
                    problems.append(f"[{name}] {key}: {error}")
            elif key not in setting_names:
                problems.append(f"[{name}] {key}: unknown setting.{_suggest(key, options)}")
            else:
                stored, error = _check_setting(getattr(current, key), value)
                if error is None:
                    changes.setdefault(name, {})[key] = stored
                else:
                    problems.append(f"[{name}] {key}: {error}")
    if problems:
        raise _error(source, problems)

    replaced: dict[str, Any] = {}
    for name, values in changes.items():
        try:
            replaced[name] = dataclasses.replace(known[name], **values)
        except (ValueError, TypeError) as exc:
            problems.append(f"[{name}] {exc}")
            continue
        invalid = _invalid_exercise(base, base_catalog, name, replaced[name])
        if invalid is not None:
            problems.append(f"[{name}] {invalid}")
    if problems:
        raise _error(source, problems)

    config = dataclasses.replace(base, **replaced)
    return Calibration(config, catalog_for(config, disabled), disabled, source)


def changed_settings(base: AppConfig, config: AppConfig) -> list[tuple[str, str, Any, Any]]:
    """(section, setting, default, value) for every setting that differs from the defaults."""
    defaults, current = sections(base), sections(config)
    return [
        (section, f.name, getattr(defaults[section], f.name), getattr(current[section], f.name))
        for section in ordered_sections(base)
        for f in dataclasses.fields(defaults[section])
        if getattr(defaults[section], f.name) != getattr(current[section], f.name)
    ]


def summarize(base: AppConfig, calibration: Calibration) -> str:
    changed = len(changed_settings(base, calibration.config))
    off = sum(len(rule_ids) for rule_ids in calibration.disabled_rules.values())
    return f"{changed} setting(s) changed, {off} check(s) switched off"


def render_template(base: AppConfig) -> str:
    """A calibration file listing every setting with its default, all commented out."""
    catalog = catalog_for(base)
    known = sections(base)
    parts = [_HEADER]
    for name in ordered_sections(base):
        key = SECTION_EXERCISES.get(name)
        lines: list[str] = []
        if key is not None:
            exercise = catalog[key]
            rules = ", ".join(rule.rule_id for rule in exercise.rules)
            lines.append(f"# {exercise.name}: rules are {rules}")
        lines.append(f"[{name}]")
        lines += [f"# {f.name} = {_toml(getattr(known[name], f.name))}"
                  for f in dataclasses.fields(known[name])]
        if key is not None:
            lines.append(f"# {DISABLED_RULES} = []")
        parts.append("\n".join(lines) + "\n")
    return "\n".join(parts)


def render_effective(base: AppConfig, calibration: Calibration, only: str | None = None) -> str:
    """The settings the app will use, with calibrated values marked."""
    defaults, current = sections(base), sections(calibration.config)
    blocks: list[str] = []
    for name in ordered_sections(base):
        if only is not None and name != only:
            continue
        key = SECTION_EXERCISES.get(name)
        title = f"[{name}]" + (f"  {calibration.catalog[key].name}" if key is not None else "")
        fields = dataclasses.fields(current[name])
        width = max(len(f.name) for f in fields)
        lines = [title]
        for f in fields:
            default, value = getattr(defaults[name], f.name), getattr(current[name], f.name)
            note = f"   (default {_toml(default)})  <- calibrated" if value != default else ""
            lines.append(f"  {f.name:<{width}} = {_toml(value)}{note}")
        off = calibration.disabled_rules.get(name, ())
        if off:
            listed = ", ".join(f'"{rule_id}"' for rule_id in off)
            lines.append(f"  {DISABLED_RULES} = [{listed}]   <- these checks are off")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


# -- helpers ---------------------------------------------------------------------------


def _check_setting(current: Any, value: Any) -> tuple[Any, str | None]:
    """The value to store, converted to the setting's type, or an error message."""
    if isinstance(current, bool):
        if isinstance(value, bool):
            return value, None
        return None, f"expected true or false, got {value!r}"
    if isinstance(current, int):
        if isinstance(value, int) and not isinstance(value, bool):
            return value, None
        return None, f"expected a whole number, got {value!r}"
    if isinstance(current, float):
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
            return float(value), None
        return None, f"expected a number, got {value!r}"
    return None, "this setting cannot be calibrated"


def _check_rule_list(value: Any, valid: Collection[str]) -> tuple[tuple[str, ...], str | None]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return (), 'expected a list of rule names, for example ["control"]'
    unknown = [item for item in value if item not in valid]
    if unknown:
        listed = ", ".join(repr(item) for item in unknown)
        return (), f"unknown rule {listed}. Valid: {', '.join(sorted(valid))}."
    return tuple(dict.fromkeys(value)), None  # drops duplicates, keeps order


def _invalid_exercise(
    base: AppConfig, base_catalog: Mapping[str, Exercise], name: str, settings: Any
) -> str | None:
    """Why these settings do not make a working exercise, or None if they do."""
    try:
        catalog = catalog_for(dataclasses.replace(base, **{name: settings}))
    except ValueError as exc:
        return f"{exc} (check the rest_* and leave_* settings)"
    key = SECTION_EXERCISES.get(name)
    if key is None:
        return None
    before, after = base_catalog[key].thresholds, catalog[key].thresholds
    if before.dips != after.dips:
        return (
            "the rest and leave values cross over: they must stay on the same sides of each "
            f"other as the defaults (rest {before.rest_angle:g}, leave {before.leave_angle:g}), "
            "otherwise rep counting runs backwards"
        )
    return None


def _suggest(name: str, options: Collection[str]) -> str:
    close = difflib.get_close_matches(name, list(options), n=1)
    if close:
        return f" Did you mean '{close[0]}'?"
    return f" Valid: {', '.join(sorted(options))}."


def _error(source: Path | None, problems: Sequence[str]) -> CalibrationError:
    name = source.name if source is not None else "The calibration data"
    count = len(problems)
    lines = [f"{name} has {count} problem{'s' if count != 1 else ''}:"]
    lines += [f"  - {problem}" for problem in problems]
    lines.append("Fix them, then run: python -m pose_tracker.calibrate check")
    return CalibrationError("\n".join(lines))


def _toml(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return repr(value)  # 55.0 stays 55.0 and 1500 stays 1500, both valid TOML