from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

MAX_REPS = 999
MAX_WEIGHT_KG = 1000.0


@dataclass(frozen=True, slots=True)
class ProgressEntry:
    """What a saved set records: its reps and its weight (None = bodyweight)."""

    reps: int
    weight_kg: float | None = None

    def __post_init__(self) -> None:
        if not 1 <= self.reps <= MAX_REPS:
            raise ValueError(f"Reps must be between 1 and {MAX_REPS}")
        weight = self.weight_kg
        if weight is not None and not (math.isfinite(weight) and 0 < weight <= MAX_WEIGHT_KG):
            raise ValueError(f"Weight must be more than 0 and at most {MAX_WEIGHT_KG:.0f} kg")


@dataclass(frozen=True, slots=True)
class ProgressSet:
    session_id: int
    exercise_key: str
    exercise_name: str
    performed_at: datetime
    reps: int
    weight_kg: float | None


@dataclass(frozen=True, slots=True)
class DayProgress:
    day: date
    sets: tuple[ProgressSet, ...]

    @property
    def reps(self) -> tuple[int, ...]:
        return tuple(s.reps for s in self.sets)

    @property
    def weights(self) -> tuple[float, ...]:
        """Per-set weights; a bodyweight set counts as 0 kg."""
        return tuple(s.weight_kg or 0.0 for s in self.sets)

    @property
    def total_reps(self) -> int:
        return sum(self.reps)

    @property
    def weighted_volume(self) -> float:
        return sum(s.reps * (s.weight_kg or 0.0) for s in self.sets)


@dataclass(frozen=True, slots=True)
class ProgressChartData:
    days: tuple[DayProgress, ...]

    @property
    def has_weights(self) -> bool:
        return any(s.weight_kg is not None for day in self.days for s in day.sets)

    @property
    def volume_unit(self) -> str:
        return "kg" if self.has_weights else "reps"

    @property
    def volumes(self) -> tuple[float, ...]:
        """Per day: sum(weight x reps) if any set has a weight, otherwise the total reps."""
        if self.has_weights:
            return tuple(day.weighted_volume for day in self.days)
        return tuple(float(day.total_reps) for day in self.days)

    @property
    def summary_text(self) -> str:
        sets = sum(len(day.sets) for day in self.days)
        return (
            f"{_plural(len(self.days), 'training day')} · {_plural(sets, 'set')} · "
            f"{format_value(sum(self.volumes))} {self.volume_unit} total volume"
        )


def build_chart_data(sets: Sequence[ProgressSet]) -> ProgressChartData:
    """Group sets by calendar day, oldest first, keeping each day's sets in order."""
    by_day: dict[date, list[ProgressSet]] = defaultdict(list)
    for progress_set in sorted(sets, key=lambda s: (s.performed_at, s.session_id)):
        by_day[progress_set.performed_at.date()].append(progress_set)
    return ProgressChartData(
        tuple(DayProgress(day, tuple(day_sets)) for day, day_sets in sorted(by_day.items()))
    )


def parse_weight(text: str) -> float | None:
    """Weight from user input. Empty means bodyweight; a comma is accepted as the decimal mark."""
    cleaned = text.strip().lower().removesuffix("kg").strip().replace(",", ".")
    if not cleaned:
        return None
    try:
        return round(float(cleaned), 2)
    except ValueError:
        raise ValueError("Enter the weight as a number, for example 42.5") from None


def format_value(value: float) -> str:
    """Up to two decimals, no trailing zeros, thousands separated: 1580 -> '1,580'."""
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def describe_day(day: DayProgress) -> str:
    return ", ".join(
        f"{format_value(s.weight_kg)} kg × {s.reps}" if s.weight_kg is not None else f"{s.reps} reps"
        for s in day.sets
    )


def describe_entry(entry: ProgressEntry) -> str:
    if entry.weight_kg is None:
        return f"{_plural(entry.reps, 'rep')} (bodyweight)"
    return f"{format_value(entry.weight_kg)} kg × {_plural(entry.reps, 'rep')}"


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"