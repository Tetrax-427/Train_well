from __future__ import annotations

from datetime import datetime

import pytest

from pose_tracker.application.progress_presenter import ProgressPresenter
from pose_tracker.domain.progress import ProgressEntry, ProgressSet

NOW = datetime(2026, 10, 15, 18, 0)


def make_set(day: int, reps: int, weight: float | None, hour: int = 10, key: str = "squat") -> ProgressSet:
    return ProgressSet(day * 100 + hour, key, key.title(), datetime(2026, 10, day, hour), reps, weight)


class FakeStore:
    def __init__(self, *sets: ProgressSet) -> None:
        self.sets = list(sets)
        self.since_seen: list[datetime | None] = []
        self.saved: list[tuple[int, ProgressEntry]] = []
        self.removed: list[int] = []

    def list_progress_sets(self, exercise_key: str, since: datetime | None = None) -> list[ProgressSet]:
        self.since_seen.append(since)
        return [
            s for s in self.sets
            if s.exercise_key == exercise_key and (since is None or s.performed_at >= since)
        ]

    def latest_progress_day(self, exercise_key: str) -> list[ProgressSet]:
        mine = [s for s in self.sets if s.exercise_key == exercise_key]
        if not mine:
            return []
        newest = max(s.performed_at.date() for s in mine)
        return [s for s in mine if s.performed_at.date() == newest]

    def save_progress(self, session_id: int, entry: ProgressEntry) -> None:
        self.saved.append((session_id, entry))

    def remove_progress(self, session_id: int) -> None:
        self.removed.append(session_id)


def make_presenter(store: FakeStore) -> ProgressPresenter:
    return ProgressPresenter(store, store, {"squat": "Squat", "push_up": "Push-up"}, lambda: NOW)


def test_options() -> None:
    presenter = make_presenter(FakeStore())
    assert presenter.exercise_options() == (("squat", "Squat"), ("push_up", "Push-up"))
    assert presenter.range_options()[0] == (2, "Last 2 days")
    assert presenter.range_options()[-1] == (None, "All time")


@pytest.mark.parametrize(("days", "first_day"), [(2, 14), (7, 9), (30, None), (None, None)])
def test_ranges_count_calendar_days_including_today(days: int | None, first_day: int | None) -> None:
    store = FakeStore()
    make_presenter(store).chart("squat", days)
    if days is None or days == 30:
        # 30 days back from Oct 15 is Sep 16; "all time" has no lower bound
        expected = None if days is None else datetime(2026, 9, 16)
    else:
        expected = datetime(2026, 10, first_day)
    assert store.since_seen == [expected]


def test_chart_only_contains_sets_in_range() -> None:
    store = FakeStore(make_set(12, 10, 40), make_set(14, 12, 40), make_set(15, 10, 50))
    data = make_presenter(store).chart("squat", 2)
    assert [d.day.day for d in data.days] == [14, 15]


def test_invalid_range_is_rejected() -> None:
    with pytest.raises(ValueError):
        make_presenter(FakeStore()).chart("squat", 0)


def test_last_time_describes_the_most_recent_saved_day() -> None:
    store = FakeStore(
        make_set(10, 9, 30), make_set(14, 12, 40, 10), make_set(14, 10, 50, 11),
        make_set(14, 8, 60, 9, key="push_up"),
    )
    assert make_presenter(store).last_time("squat") == "Last time (14 Oct): 40 kg × 12, 50 kg × 10"


def test_last_time_is_none_without_saved_sets() -> None:
    assert make_presenter(FakeStore()).last_time("squat") is None


def test_save_parses_the_weight_and_describes_the_result() -> None:
    store = FakeStore()
    assert make_presenter(store).save(7, "42,5", 12) == "42.5 kg × 12 reps"
    assert store.saved == [(7, ProgressEntry(12, 42.5))]


def test_save_without_a_weight_is_bodyweight() -> None:
    store = FakeStore()
    assert make_presenter(store).save(7, "", 15) == "15 reps (bodyweight)"
    assert store.saved == [(7, ProgressEntry(15, None))]


@pytest.mark.parametrize(("text", "reps"), [("heavy", 10), ("40", 0), ("-5", 10)])
def test_invalid_input_saves_nothing(text: str, reps: int) -> None:
    store = FakeStore()
    with pytest.raises(ValueError):
        make_presenter(store).save(7, text, reps)
    assert store.saved == []


def test_remove_forwards_to_the_store() -> None:
    store = FakeStore()
    make_presenter(store).remove(7)
    assert store.removed == [7]