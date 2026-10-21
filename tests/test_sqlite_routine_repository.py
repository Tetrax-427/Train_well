from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path
import threading
import pytest

from pose_tracker.domain.routine import Routine
from pose_tracker.errors import PersistenceError
from pose_tracker.infrastructure.sqlite_routine_repository import SqliteRoutineRepository


@pytest.fixture
def repo(tmp_path: Path) -> Iterator[SqliteRoutineRepository]:
    repository = SqliteRoutineRepository(tmp_path / "routines.db")
    yield repository
    repository.close()


def count_exercise_rows(path: Path) -> int:
    connection = sqlite3.connect(path)
    try:
        return connection.execute("SELECT COUNT(*) FROM routine_exercises").fetchone()[0]
    finally:
        connection.close()


def test_starts_empty(repo: SqliteRoutineRepository) -> None:
    assert repo.list_routines() == []
    assert repo.get_routine(1) is None


def test_create_and_read_back_keeps_the_exercise_order(repo: SqliteRoutineRepository) -> None:
    created = repo.create_routine("Push", ["shoulder_press", "bench_press", "plank"])
    assert created.name == "Push"
    assert created.exercise_keys == ("shoulder_press", "bench_press", "plank")
    assert repo.get_routine(created.routine_id) == created
    assert repo.list_routines() == [created]


def test_routines_are_listed_in_creation_order(repo: SqliteRoutineRepository) -> None:
    repo.create_routine("Pull", ["row"])
    repo.create_routine("Legs", ["squat"])
    repo.create_routine("Arms", ["curl"])
    assert [r.name for r in repo.list_routines()] == ["Pull", "Legs", "Arms"]


def test_names_are_unique_ignoring_case(repo: SqliteRoutineRepository) -> None:
    repo.create_routine("Push", ["squat"])
    with pytest.raises(ValueError, match="already exists"):
        repo.create_routine("push", ["plank"])
    assert [r.name for r in repo.list_routines()] == ["Push"]


def test_update_changes_the_name_and_exercises(repo: SqliteRoutineRepository) -> None:
    routine = repo.create_routine("Push", ["squat", "plank"])
    repo.update_routine(routine.routine_id, "PUSH", ["plank", "curl", "squat"])
    assert repo.get_routine(routine.routine_id) == Routine(
        routine.routine_id, "PUSH", ("plank", "curl", "squat")
    )


def test_renaming_to_another_routines_name_is_rejected(repo: SqliteRoutineRepository) -> None:
    repo.create_routine("Push", ["squat"])
    pull = repo.create_routine("Pull", ["row"])
    with pytest.raises(ValueError, match="already exists"):
        repo.update_routine(pull.routine_id, "push", ["row"])
    assert repo.get_routine(pull.routine_id) == pull


def test_updating_a_missing_routine_fails(repo: SqliteRoutineRepository) -> None:
    with pytest.raises(PersistenceError):
        repo.update_routine(99, "Ghost", ["squat"])


def test_delete_removes_the_routine_and_only_its_exercises(
    tmp_path: Path, repo: SqliteRoutineRepository
) -> None:
    push = repo.create_routine("Push", ["bench_press", "plank"])
    legs = repo.create_routine("Legs", ["squat"])
    repo.delete_routine(push.routine_id)
    assert repo.list_routines() == [legs]
    assert count_exercise_rows(tmp_path / "routines.db") == 1


def test_a_failed_write_rolls_back_everything(
    tmp_path: Path, repo: SqliteRoutineRepository
) -> None:
    with pytest.raises(PersistenceError):
        repo.create_routine("Broken", ["squat", "squat"])  # the same exercise twice
    assert repo.list_routines() == []
    assert count_exercise_rows(tmp_path / "routines.db") == 0


def test_data_survives_reopening(tmp_path: Path) -> None:
    path = tmp_path / "routines.db"
    first = SqliteRoutineRepository(path)
    created = first.create_routine("Push", ["bench_press"])
    first.close()

    second = SqliteRoutineRepository(path)
    assert second.list_routines() == [created]
    second.close()


def test_a_newer_database_version_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "routines.db"
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA user_version = 99")
    connection.commit()
    connection.close()
    with pytest.raises(PersistenceError):
        SqliteRoutineRepository(path)


def test_an_unusable_location_is_a_persistence_error(tmp_path: Path) -> None:
    blocker = tmp_path / "not_a_directory"
    blocker.write_text("x")
    with pytest.raises(PersistenceError):
        SqliteRoutineRepository(blocker / "routines.db")

def test_it_can_be_read_from_another_thread(repo: SqliteRoutineRepository) -> None:
    repo.create_routine("Push", ["bench_press"])
    found: list[str] = []
    thread = threading.Thread(target=lambda: found.extend(r.name for r in repo.list_routines()))
    thread.start()
    thread.join()
    assert found == ["Push"]