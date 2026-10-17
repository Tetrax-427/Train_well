from __future__ import annotations

from datetime import date, datetime

import pytest

from pose_tracker.domain.progress import (
    ProgressEntry,
    ProgressSet,
    build_chart_data,
    describe_day,
    describe_entry,
    format_value,
    parse_weight,
)


def make_set(day: int, reps: int, weight: float | None, hour: int = 10) -> ProgressSet:
    return ProgressSet(hour, "squat", "Squat", datetime(2026, 10, day, hour), reps, weight)


DAY1 = [make_set(10, 12, 40, 10), make_set(10, 10, 50, 11), make_set(10, 10, 60, 12)]
DAY2 = [make_set(11, 15, 40, 10), make_set(11, 12, 50, 11), make_set(11, 10, 60, 12)]
DAY3 = [
    make_set(14, 15, 40, 10), make_set(14, 12, 50, 11),
    make_set(14, 10, 60, 12), make_set(14, 7, 40, 13),
]


def test_chart_data_for_three_training_days() -> None:
    data = build_chart_data(DAY1 + DAY2 + DAY3)
    assert [d.day for d in data.days] == [date(2026, 10, 10), date(2026, 10, 11), date(2026, 10, 14)]
    assert [d.reps for d in data.days] == [(12, 10, 10), (15, 12, 10), (15, 12, 10, 7)]
    assert [d.weights for d in data.days] == [(40, 50, 60), (40, 50, 60), (40, 50, 60, 40)]
    assert data.has_weights and data.volume_unit == "kg"
    assert data.volumes == (1580, 1800, 2080)
    assert data.summary_text == "3 training days · 10 sets · 5,460 kg total volume"


def test_input_order_does_not_matter() -> None:
    shuffled = [DAY3[2], DAY1[1], DAY2[0], DAY3[0], DAY1[0], DAY2[2], DAY3[1], DAY1[2], DAY3[3], DAY2[1]]
    data = build_chart_data(shuffled)
    assert [d.reps for d in data.days] == [(12, 10, 10), (15, 12, 10), (15, 12, 10, 7)]


def test_bodyweight_volume_is_the_total_reps() -> None:
    data = build_chart_data([make_set(10, 15, None, 10), make_set(10, 12, None, 11), make_set(11, 10, None)])
    assert not data.has_weights and data.volume_unit == "reps"
    assert data.volumes == (27, 10)
    assert data.summary_text == "2 training days · 3 sets · 37 reps total volume"


def test_unweighted_sets_count_as_zero_kg_in_a_weighted_chart() -> None:
    data = build_chart_data([make_set(10, 12, 40, 10), make_set(10, 10, None, 11)])
    assert data.days[0].weights == (40, 0)
    assert data.volumes == (480,)


def test_empty_input_has_no_days() -> None:
    data = build_chart_data([])
    assert data.days == () and data.volumes == ()


def test_describe_day_and_entry() -> None:
    assert describe_day(build_chart_data(DAY1).days[0]) == "40 kg × 12, 50 kg × 10, 60 kg × 10"
    assert describe_day(build_chart_data([make_set(10, 12, None)]).days[0]) == "12 reps"
    assert describe_entry(ProgressEntry(12, 42.5)) == "42.5 kg × 12 reps"
    assert describe_entry(ProgressEntry(1, 40.0)) == "40 kg × 1 rep"
    assert describe_entry(ProgressEntry(12)) == "12 reps (bodyweight)"


@pytest.mark.parametrize(("text", "expected"), [
    ("42.5", 42.5), ("42,5", 42.5), (" 40 kg ", 40.0), ("", None), ("   ", None),
    ("40.126", 40.13),
])
def test_parse_weight(text: str, expected: float | None) -> None:
    assert parse_weight(text) == expected


def test_parse_weight_rejects_text() -> None:
    with pytest.raises(ValueError):
        parse_weight("heavy")


@pytest.mark.parametrize(("reps", "weight"), [
    (0, None), (1000, None), (10, 0.0), (10, -5.0), (10, float("nan")),
    (10, float("inf")), (10, 1000.5),
])
def test_invalid_entries_are_rejected(reps: int, weight: float | None) -> None:
    with pytest.raises(ValueError):
        ProgressEntry(reps, weight)


def test_valid_entries_are_accepted() -> None:
    assert ProgressEntry(1, 0.5).weight_kg == 0.5
    assert ProgressEntry(999, 1000.0).reps == 999
    assert ProgressEntry(10).weight_kg is None


@pytest.mark.parametrize(("value", "expected"), [
    (1580.0, "1,580"), (40.0, "40"), (42.5, "42.5"), (42.55, "42.55"), (0, "0"), (100.0, "100"),
])
def test_format_value(value: float, expected: str) -> None:
    assert format_value(value) == expected