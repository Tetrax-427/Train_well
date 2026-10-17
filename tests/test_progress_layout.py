from __future__ import annotations

import pytest

from pose_tracker.application.progress_layout import (
    DAY_GAP,
    LEFT_MARGIN,
    MAX_BAR_WIDTH,
    MIN_BAR_WIDTH,
    MIN_SLOT_WIDTH,
    compute_layout,
    nice_axis,
)


def test_few_days_use_full_size_bars() -> None:
    layout = compute_layout([3, 3, 4], 2000)
    assert layout.bar_width == MAX_BAR_WIDTH
    assert layout.total_width <= 2000


def test_bars_shrink_before_the_chart_scrolls() -> None:
    layout = compute_layout([3] * 8, 1200)
    assert MIN_BAR_WIDTH < layout.bar_width < MAX_BAR_WIDTH
    assert 1190 < layout.total_width <= 1200


def test_bars_stop_shrinking_at_the_minimum_and_the_chart_scrolls() -> None:
    layout = compute_layout([3] * 8, 500)
    assert layout.bar_width == MIN_BAR_WIDTH
    assert layout.total_width > 500


def test_slots_are_ordered_and_do_not_overlap() -> None:
    layout = compute_layout([1, 4, 2], 2000)
    assert layout.slots[0].left >= LEFT_MARGIN + DAY_GAP - 1e-9
    for first, second in zip(layout.slots, layout.slots[1:]):
        assert second.left >= first.left + first.width + DAY_GAP - 1e-9


def test_a_single_set_still_gets_a_readable_slot_with_its_bar_centered() -> None:
    slot = compute_layout([1], 2000).slots[0]
    assert slot.width == MIN_SLOT_WIDTH
    assert slot.bars_left == pytest.approx(slot.left + (MIN_SLOT_WIDTH - MAX_BAR_WIDTH) / 2)


def test_a_day_without_sets_is_rejected() -> None:
    with pytest.raises(ValueError):
        compute_layout([3, 0], 1000)


@pytest.mark.parametrize(("value", "axis_max", "step"), [
    (12, 15, 5), (60, 60, 20), (1580, 2000, 500), (10, 10, 5), (7, 8, 2), (0, 1, 1),
])
def test_nice_axis(value: float, axis_max: float, step: float) -> None:
    assert nice_axis(value) == (pytest.approx(axis_max), pytest.approx(step))