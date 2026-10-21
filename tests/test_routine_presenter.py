from __future__ import annotations

from collections.abc import Sequence

import pytest

from pose_tracker.application.routine_presenter import RoutinePresenter
from pose_tracker.domain.routine import Routine

NAMES = {
    "squat": "Squat",
    "bench_press": "Bench Press",
    "row": "Bent-Over Row",
    "curl": "Bicep Curl",
    "plank": "Plank",
}
PUSH = Routine(1, "Push", ("bench_press", "plank"))
LEGS = Routine(2, "Legs", ("squat",))


class FakeStore:
    def __init__(self, *routines: Routine) -> None:
        self.routines = {routine.routine_id: routine for routine in routines}
        self._next = max(self.routines, default=0) + 1

    def list_routines(self) -> list[Routine]:
        return list(self.routines.values())

    def get_routine(self, routine_id: int) -> Routine | None:
        return self.routines.get(routine_id)

    def create_routine(self, name: str, exercise_keys: Sequence[str]) -> Routine:
        self._require_free_name(name, own_id=None)
        routine = Routine(self._next, name, tuple(exercise_keys))
        self.routines[self._next] = routine
        self._next += 1
        return routine

    def update_routine(self, routine_id: int, name: str, exercise_keys: Sequence[str]) -> None:
        self._require_free_name(name, own_id=routine_id)
        self.routines[routine_id] = Routine(routine_id, name, tuple(exercise_keys))

    def delete_routine(self, routine_id: int) -> None:
        self.routines.pop(routine_id, None)

    def _require_free_name(self, name: str, own_id: int | None) -> None:
        for routine in self.routines.values():
            if routine.name.lower() == name.lower() and routine.routine_id != own_id:
                raise ValueError(f"A routine named '{name}' already exists.")


def make(*routines: Routine) -> tuple[RoutinePresenter, FakeStore]:
    store = FakeStore(*routines)
    return RoutinePresenter(store, NAMES), store


def test_exercise_options_follow_the_catalog_order() -> None:
    assert make()[0].exercise_options() == tuple(NAMES.items())


def test_create_cleans_the_name_and_returns_the_new_id() -> None:
    presenter, store = make()
    routine_id = presenter.create("  Pull   day ", ["row", "curl"])
    assert store.routines[routine_id] == Routine(routine_id, "Pull day", ("row", "curl"))


@pytest.mark.parametrize(("name", "keys"), [
    ("", ["squat"]),
    ("Legs", []),
    ("Legs", ["squat", "squat"]),
    ("Legs", ["deadlift"]),
])
def test_invalid_routines_are_not_saved(name: str, keys: list[str]) -> None:
    presenter, store = make()
    with pytest.raises(ValueError):
        presenter.create(name, keys)
    assert store.routines == {}


def test_names_must_be_unique_ignoring_case() -> None:
    presenter, _ = make(PUSH)
    with pytest.raises(ValueError, match="already exists"):
        presenter.create("push", ["squat"])


def test_a_routine_can_keep_its_own_name_when_edited() -> None:
    presenter, store = make(PUSH)
    presenter.update(1, "PUSH", ["plank", "bench_press"])
    assert store.routines[1] == Routine(1, "PUSH", ("plank", "bench_press"))


def test_an_invalid_update_changes_nothing() -> None:
    presenter, store = make(PUSH)
    with pytest.raises(ValueError):
        presenter.update(1, "Push", [])
    assert store.routines[1] == PUSH


def test_rows_summarize_the_exercises() -> None:
    everything = Routine(3, "Everything", ("squat", "bench_press", "row", "curl", "plank"))
    first, second = make(PUSH, everything)[0].routines()
    assert (first.title, first.subtitle) == ("Push", "Bench Press, Plank")
    assert second.subtitle == "Squat, Bench Press, Bent-Over Row +2 more"


def test_a_routine_with_no_known_exercises_says_so() -> None:
    [row] = make(Routine(1, "Old", ("deadlift",)))[0].routines()
    assert row.subtitle == "No exercises available"


def test_routine_options_start_with_all_exercises() -> None:
    assert make(PUSH, LEGS)[0].routine_options() == (
        (None, "All exercises"), (1, "Push"), (2, "Legs")
    )


def test_a_routines_exercises_follow_its_own_order() -> None:
    assert make(PUSH)[0].exercises_for(1) == (("bench_press", "Bench Press"), ("plank", "Plank"))


def test_all_exercises_or_a_missing_routine_show_everything() -> None:
    presenter, _ = make(PUSH)
    everything = tuple(NAMES.items())
    assert presenter.exercises_for(None) == everything
    assert presenter.exercises_for(99) == everything


def test_exercises_that_no_longer_exist_are_dropped() -> None:
    presenter, _ = make(Routine(1, "Old", ("squat", "deadlift", "plank")))
    expected = (("squat", "Squat"), ("plank", "Plank"))
    assert presenter.exercises_for(1) == expected
    detail = presenter.load(1)
    assert detail is not None and detail.exercises == expected


def test_loading_a_missing_routine_gives_none() -> None:
    assert make()[0].load(5) is None


def test_delete_removes_the_routine() -> None:
    presenter, store = make(PUSH)
    presenter.delete(1)
    assert store.routines == {}