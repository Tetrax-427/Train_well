from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from pose_tracker.domain.routine import Routine, clean_exercises, clean_name
from pose_tracker.interfaces import RoutineStore

_NAMES_IN_ROW = 3


@dataclass(frozen=True, slots=True)
class RoutineRow:
    routine_id: int
    title: str
    subtitle: str


@dataclass(frozen=True, slots=True)
class RoutineDetail:
    routine_id: int
    name: str
    exercises: tuple[tuple[str, str], ...]  # (key, display name), in routine order


class RoutinePresenter:
    """Creating, editing and listing routines. Holds no Qt code."""

    def __init__(self, store: RoutineStore, exercise_names: Mapping[str, str]) -> None:
        self._store = store
        self._names = dict(exercise_names)

    def exercise_options(self) -> tuple[tuple[str, str], ...]:
        """Every exercise as (key, name), in the order the app lists them."""
        return tuple(self._names.items())

    def routines(self) -> tuple[RoutineRow, ...]:
        return tuple(self._row(routine) for routine in self._store.list_routines())

    def routine_options(self) -> tuple[tuple[int | None, str], ...]:
        """Choices for the Train tab: everything, or one routine."""
        return (
            (None, "All exercises"),
            *((routine.routine_id, routine.name) for routine in self._store.list_routines()),
        )

    def exercises_for(self, routine_id: int | None) -> tuple[tuple[str, str], ...]:
        """The exercises to offer: a routine's own, in order, or all of them."""
        if routine_id is None:
            return self.exercise_options()
        routine = self._store.get_routine(routine_id)
        if routine is None:
            return self.exercise_options()
        return self._named(routine.exercise_keys)

    def load(self, routine_id: int) -> RoutineDetail | None:
        routine = self._store.get_routine(routine_id)
        if routine is None:
            return None
        return RoutineDetail(routine.routine_id, routine.name, self._named(routine.exercise_keys))

    def create(self, name: str, exercise_keys: Sequence[str]) -> int:
        """Save a new routine and return its id. Raises ValueError for invalid input."""
        cleaned, keys = self._validated(name, exercise_keys)
        return self._store.create_routine(cleaned, keys).routine_id

    def update(self, routine_id: int, name: str, exercise_keys: Sequence[str]) -> None:
        cleaned, keys = self._validated(name, exercise_keys)
        self._store.update_routine(routine_id, cleaned, keys)

    def delete(self, routine_id: int) -> None:
        self._store.delete_routine(routine_id)

    # -- helpers ---------------------------------------------------------------------

    def _validated(self, name: str, exercise_keys: Sequence[str]) -> tuple[str, tuple[str, ...]]:
        return clean_name(name), clean_exercises(exercise_keys, self._names)

    def _named(self, keys: Sequence[str]) -> tuple[tuple[str, str], ...]:
        """(key, name) pairs, dropping exercises that no longer exist."""
        return tuple((key, self._names[key]) for key in keys if key in self._names)

    def _row(self, routine: Routine) -> RoutineRow:
        names = [name for _, name in self._named(routine.exercise_keys)]
        subtitle = ", ".join(names[:_NAMES_IN_ROW])
        if len(names) > _NAMES_IN_ROW:
            subtitle += f" +{len(names) - _NAMES_IN_ROW} more"
        return RoutineRow(routine.routine_id, routine.name, subtitle or "No exercises available")