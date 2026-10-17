from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

MIN_BAR_WIDTH = 24.0
MAX_BAR_WIDTH = 48.0
BAR_GAP = 4.0
DAY_GAP = 30.0
MIN_SLOT_WIDTH = 52.0  # wide enough for a date label under a single bar
LEFT_MARGIN = 56.0     # room for the y-axis labels


@dataclass(frozen=True, slots=True)
class Slot:
    """The horizontal space of one day."""

    left: float
    width: float
    bars_left: float  # the bars are centered inside the slot

    @property
    def center(self) -> float:
        return self.left + self.width / 2


@dataclass(frozen=True, slots=True)
class ChartLayout:
    bar_width: float
    slots: tuple[Slot, ...]
    total_width: float


def _build(sets_per_day: Sequence[int], bar_width: float) -> ChartLayout:
    x = LEFT_MARGIN
    slots: list[Slot] = []
    for count in sets_per_day:
        bars = count * bar_width + (count - 1) * BAR_GAP
        width = max(bars, MIN_SLOT_WIDTH)
        x += DAY_GAP
        slots.append(Slot(x, width, x + (width - bars) / 2))
        x += width
    return ChartLayout(bar_width, tuple(slots), x + DAY_GAP)


def compute_layout(sets_per_day: Sequence[int], viewport_width: float) -> ChartLayout:
    """Full-size bars if they fit; otherwise the widest bars that fit, never below the
    minimum. If even minimum bars do not fit, the chart is wider than the viewport (scrolls)."""
    if any(count < 1 for count in sets_per_day):
        raise ValueError("Every day needs at least one set")
    widest = _build(sets_per_day, MAX_BAR_WIDTH)
    if widest.total_width <= viewport_width:
        return widest
    narrowest = _build(sets_per_day, MIN_BAR_WIDTH)
    if narrowest.total_width >= viewport_width:
        return narrowest
    low, high = MIN_BAR_WIDTH, MAX_BAR_WIDTH
    for _ in range(40):
        middle = (low + high) / 2
        if _build(sets_per_day, middle).total_width <= viewport_width:
            low = middle
        else:
            high = middle
    return _build(sets_per_day, low)


def nice_axis(max_value: float, target_ticks: int = 4) -> tuple[float, float]:
    """(axis maximum, tick step) with round tick values that cover ``max_value``."""
    if max_value <= 0:
        return 1.0, 1.0
    raw = max_value / target_ticks
    base = 10.0 ** math.floor(math.log10(raw))
    step = base
    for multiple in (1, 2, 5, 10):
        step = multiple * base
        if step >= raw - 1e-12:
            break
    return math.ceil(max_value / step - 1e-9) * step, step