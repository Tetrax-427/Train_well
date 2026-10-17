from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, time, timedelta

from pose_tracker.domain.progress import (
    ProgressChartData,
    ProgressEntry,
    build_chart_data,
    describe_day,
    describe_entry,
    parse_weight,
)
from pose_tracker.interfaces import ProgressReader, ProgressWriter

RANGES: tuple[tuple[int | None, str], ...] = (
    (2, "Last 2 days"),
    (7, "Last 7 days"),
    (30, "Last 30 days"),
    (90, "Last 90 days"),
    (None, "All time"),
)


class ProgressPresenter:
    """Saving sets to progress, and the data behind the Progress tab. Holds no Qt code."""

    def __init__(
        self,
        reader: ProgressReader,
        writer: ProgressWriter,
        exercise_names: Mapping[str, str],
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._names = dict(exercise_names)
        self._clock = clock

    def exercise_options(self) -> tuple[tuple[str, str], ...]:
        return tuple(self._names.items())

    def range_options(self) -> tuple[tuple[int | None, str], ...]:
        return RANGES

    def chart(self, exercise_key: str, days: int | None) -> ProgressChartData:
        """Saved sets of one exercise over the last ``days`` calendar days (today included)."""
        since: datetime | None = None
        if days is not None:
            if days < 1:
                raise ValueError("days must be at least 1")
            since = datetime.combine(self._clock().date() - timedelta(days=days - 1), time.min)
        return build_chart_data(self._reader.list_progress_sets(exercise_key, since))

    def last_time(self, exercise_key: str) -> str | None:
        """What you did on your most recent saved day of this exercise, or None."""
        sets = self._reader.latest_progress_day(exercise_key)
        if not sets:
            return None
        day = build_chart_data(sets).days[-1]
        return f"Last time ({day.day:%d %b}): {describe_day(day)}"

    def save(self, session_id: int, weight_text: str, reps: int) -> str:
        """Save or update a session's set. Raises ValueError for invalid input."""
        entry = ProgressEntry(reps, parse_weight(weight_text))
        self._writer.save_progress(session_id, entry)
        return describe_entry(entry)

    def remove(self, session_id: int) -> None:
        self._writer.remove_progress(session_id)