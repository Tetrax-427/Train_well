from __future__ import annotations

from datetime import date, datetime

import pytest

from pose_tracker.application.chat.tool_arguments import (
    Arguments,
    TimeWindow,
    ToolArgumentError,
    resolve_exercise,
    time_window,
)

TODAY = date(2026, 10, 21)
NAMES = {"squat": "Squat", "bench_press": "Bench Press", "lat_pulldown_wide": "Lat Pulldown (Wide Grip)"}


def window(**raw: object) -> TimeWindow:
    return time_window(Arguments(raw, ("days", "start_date", "end_date")), TODAY)


def test_no_filters_means_everything() -> None:
    assert window() == TimeWindow()


def test_days_counts_today_as_the_first_day() -> None:
    assert window(days=7) == TimeWindow(since=datetime(2026, 10, 15))
    assert window(days=1) == TimeWindow(since=datetime(2026, 10, 21))


def test_a_date_range_includes_both_end_days() -> None:
    w = window(start_date="2026-10-01", end_date="2026-10-05")
    assert w == TimeWindow(since=datetime(2026, 10, 1), until=datetime(2026, 10, 6))
    assert w.contains(datetime(2026, 10, 5, 23, 59))
    assert not w.contains(datetime(2026, 10, 6))
    assert not w.contains(datetime(2026, 9, 30, 23, 59))


def test_one_sided_ranges() -> None:
    assert window(start_date="2026-10-01").until is None
    assert window(end_date="2026-10-05").since is None


@pytest.mark.parametrize("raw", [
    {"days": 7, "start_date": "2026-10-01"},
    {"start_date": "2026-10-09", "end_date": "2026-10-01"},
    {"start_date": "yesterday"},
    {"days": 0},
    {"days": 99999},
])
def test_bad_windows_are_rejected(raw: dict[str, object]) -> None:
    with pytest.raises(ToolArgumentError):
        window(**raw)


def test_unknown_arguments_are_named() -> None:
    with pytest.raises(ToolArgumentError, match="Unknown argument.*nope.*Allowed: days"):
        Arguments({"nope": 1}, ("days",))


def test_integers_accept_numeric_text_and_whole_floats_but_not_booleans() -> None:
    assert Arguments({"n": "7"}, ("n",)).integer("n", 1, 10) == 7
    assert Arguments({"n": 7.0}, ("n",)).integer("n", 1, 10) == 7
    for bad in (True, 7.5, "seven", [7]):
        with pytest.raises(ToolArgumentError, match="whole number"):
            Arguments({"n": bad}, ("n",)).integer("n", 1, 10)
    with pytest.raises(ToolArgumentError, match="between 1 and 10"):
        Arguments({"n": 11}, ("n",)).integer("n", 1, 10)


def test_missing_null_and_empty_values_mean_not_given() -> None:
    args = Arguments({"a": None, "b": ""}, ("a", "b", "c"))
    assert args.integer("a", 1, 5, default=3) == 3
    assert args.text("b") is None and args.text("c") is None
    assert args.day("c") is None
    assert args.boolean("a") is False


def test_required_integers_and_typed_values() -> None:
    with pytest.raises(ToolArgumentError, match="required"):
        Arguments({}, ("id",)).require_integer("id", 1, 9)
    with pytest.raises(ToolArgumentError, match="text"):
        Arguments({"x": 5}, ("x",)).text("x")
    with pytest.raises(ToolArgumentError, match="true or false"):
        Arguments({"x": "yes"}, ("x",)).boolean("x")


@pytest.mark.parametrize("value", ["squat", "Squat", "  SQUAT ", "bench press", "Bench Press", "bench_press"])
def test_exercises_resolve_by_key_or_name(value: str) -> None:
    assert resolve_exercise(value, NAMES) in ("squat", "bench_press")


def test_exercise_names_with_brackets_resolve() -> None:
    assert resolve_exercise("lat pulldown (wide grip)", NAMES) == "lat_pulldown_wide"


def test_unknown_exercise_lists_the_valid_keys() -> None:
    with pytest.raises(ToolArgumentError, match="Valid keys: squat, bench_press"):
        resolve_exercise("curls", NAMES)
    assert resolve_exercise(None, NAMES) is None