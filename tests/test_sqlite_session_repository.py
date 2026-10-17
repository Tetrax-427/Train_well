from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from pose_tracker.domain.history import RepRecord, ViolationRecord
from pose_tracker.domain.pose import Landmark, Pose
from pose_tracker.errors import PersistenceError
from pose_tracker.infrastructure.filesystem_snapshot_store import FileSnapshotStore
from pose_tracker.infrastructure.sqlite_session_repository import SqliteSessionRepository
from pose_tracker.domain.progress import ProgressEntry

T0 = datetime(2026, 10, 15, 15, 30, 12)
T1 = datetime(2026, 10, 15, 15, 31, 2)
JPEG = b"\xff\xd8fake-jpeg"
POSE = Pose((Landmark(0.25, 0.5, -0.1, 0.9), Landmark(0.75, 0.5, 0.0, 0.8)))


def violation(rule: str = "squat_depth", jpeg: bytes | None = JPEG) -> ViolationRecord:
    return ViolationRecord(rule, "Go deeper", "Because depth.", 118.4, 100.0, 1500, POSE, jpeg)


def rep(number: int, *violations: ViolationRecord) -> RepRecord:
    return RepRecord(number, T0, 2400, {"knee_angle": (92.1, 175.3)}, violations)


@pytest.fixture
def repo(tmp_path: Path) -> SqliteSessionRepository:
    return SqliteSessionRepository(
        tmp_path / "history.db", FileSnapshotStore(tmp_path / "snapshots")
    )


def test_round_trip_of_a_session(repo: SqliteSessionRepository) -> None:
    session_id = repo.start_session("squat", "Squat", T0)
    repo.add_rep(session_id, rep(1))
    repo.add_rep(session_id, rep(2, violation()))
    repo.finish_session(session_id, T1)

    stored = repo.get_session(session_id)
    assert stored is not None
    summary = stored.summary
    assert (summary.exercise_key, summary.exercise_name) == ("squat", "Squat")
    assert (summary.started_at, summary.ended_at) == (T0, T1)
    assert (summary.total_reps, summary.clean_reps) == (2, 1)

    clean, flawed = stored.reps
    assert clean.is_clean and not flawed.is_clean
    assert flawed.duration_ms == 2400
    assert flawed.feature_ranges == {"knee_angle": (92.1, 175.3)}

    [stored_violation] = flawed.violations
    assert stored_violation.rule_id == "squat_depth"
    assert stored_violation.explanation == "Because depth."
    assert (stored_violation.measured, stored_violation.limit) == (118.4, 100.0)
    assert stored_violation.timestamp_ms == 1500
    assert stored_violation.pose == POSE
    assert stored_violation.snapshot_path is not None
    assert stored_violation.snapshot_path.read_bytes() == JPEG


def test_sessions_are_listed_newest_first_and_can_be_filtered(
    repo: SqliteSessionRepository,
) -> None:
    older = repo.start_session("squat", "Squat", T0)
    newer = repo.start_session("deadlift", "Deadlift", T1)
    assert [s.session_id for s in repo.list_sessions()] == [newer, older]
    assert [s.session_id for s in repo.list_sessions("squat")] == [older]


def test_unknown_session_is_none(repo: SqliteSessionRepository) -> None:
    assert repo.get_session(999) is None


def test_delete_removes_rows_and_snapshots(tmp_path: Path, repo: SqliteSessionRepository) -> None:
    session_id = repo.start_session("squat", "Squat", T0)
    repo.add_rep(session_id, rep(1, violation()))
    assert (tmp_path / "snapshots" / str(session_id)).exists()

    repo.delete_session(session_id)

    assert repo.get_session(session_id) is None
    assert not (tmp_path / "snapshots" / str(session_id)).exists()


def test_violation_without_a_snapshot_has_no_path(repo: SqliteSessionRepository) -> None:
    session_id = repo.start_session("squat", "Squat", T0)
    repo.add_rep(session_id, rep(1, violation(jpeg=None)))
    stored = repo.get_session(session_id)
    assert stored is not None
    assert stored.reps[0].violations[0].snapshot_path is None


def test_snapshot_deleted_from_disk_reads_as_missing(repo: SqliteSessionRepository) -> None:
    session_id = repo.start_session("squat", "Squat", T0)
    repo.add_rep(session_id, rep(1, violation()))
    stored = repo.get_session(session_id)
    assert stored is not None and stored.reps[0].violations[0].snapshot_path is not None
    stored.reps[0].violations[0].snapshot_path.unlink()

    again = repo.get_session(session_id)
    assert again is not None
    assert again.reps[0].violations[0].snapshot_path is None


def test_snapshot_write_failure_still_saves_the_rep(tmp_path: Path) -> None:
    class FailingStore:
        def save(self, session_id: int, name: str, jpeg: bytes) -> str:
            raise OSError("disk full")

        def resolve(self, key: str) -> Path:
            return Path(key)

        def delete_session(self, session_id: int) -> None: ...

    repo = SqliteSessionRepository(tmp_path / "history.db", FailingStore())
    session_id = repo.start_session("squat", "Squat", T0)
    repo.add_rep(session_id, rep(1, violation()))
    stored = repo.get_session(session_id)
    assert stored is not None
    assert stored.reps[0].violations[0].snapshot_path is None


def test_data_survives_reopening(tmp_path: Path) -> None:
    store = FileSnapshotStore(tmp_path / "snapshots")
    first = SqliteSessionRepository(tmp_path / "history.db", store)
    session_id = first.start_session("squat", "Squat", T0)
    first.close()

    second = SqliteSessionRepository(tmp_path / "history.db", store)
    assert [s.session_id for s in second.list_sessions()] == [session_id]


def test_duplicate_rep_number_is_a_persistence_error(repo: SqliteSessionRepository) -> None:
    session_id = repo.start_session("squat", "Squat", T0)
    repo.add_rep(session_id, rep(1))
    with pytest.raises(PersistenceError):
        repo.add_rep(session_id, rep(1))


def test_newer_database_version_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "history.db"
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA user_version = 99")
    connection.commit()
    connection.close()
    with pytest.raises(PersistenceError):
        SqliteSessionRepository(path, FileSnapshotStore(tmp_path / "snapshots"))


def test_unusable_location_is_a_persistence_error(tmp_path: Path) -> None:
    blocker = tmp_path / "not_a_directory"
    blocker.write_text("x")
    with pytest.raises(PersistenceError):
        SqliteSessionRepository(blocker / "history.db", FileSnapshotStore(tmp_path / "s"))

D1, D2, D3 = (datetime(2026, 10, day, 10, 0, 0) for day in (10, 12, 12))


def saved_session(
    repo: SqliteSessionRepository, started: datetime, reps: int, weight: float | None,
    key: str = "squat",
) -> int:
    session_id = repo.start_session(key, key.title(), started)
    repo.save_progress(session_id, ProgressEntry(reps, weight))
    return session_id


def test_only_saved_sessions_appear_in_progress(repo: SqliteSessionRepository) -> None:
    saved = saved_session(repo, D1, 12, 40.0)
    repo.start_session("squat", "Squat", D2)  # never saved
    saved_session(repo, D2, 10, None, key="push_up")

    [only] = repo.list_progress_sets("squat")
    assert (only.session_id, only.reps, only.weight_kg) == (saved, 12, 40.0)
    assert only.performed_at == D1 and only.exercise_name == "Squat"


def test_progress_sets_are_filtered_by_date_and_ordered(repo: SqliteSessionRepository) -> None:
    saved_session(repo, datetime(2026, 10, 12, 11, 0), 10, 50.0)
    saved_session(repo, datetime(2026, 10, 10, 10, 0), 12, 40.0)
    saved_session(repo, datetime(2026, 10, 12, 9, 0), 15, 40.0)

    assert [s.reps for s in repo.list_progress_sets("squat")] == [12, 15, 10]
    assert [s.reps for s in repo.list_progress_sets("squat", datetime(2026, 10, 11))] == [15, 10]


def test_latest_progress_day_returns_all_sets_of_the_newest_day(repo: SqliteSessionRepository) -> None:
    saved_session(repo, datetime(2026, 10, 10, 10, 0), 12, 40.0)
    saved_session(repo, datetime(2026, 10, 12, 9, 0), 15, 40.0)
    saved_session(repo, datetime(2026, 10, 12, 11, 0), 10, 50.0)
    saved_session(repo, datetime(2026, 10, 13, 9, 0), 8, 60.0, key="push_up")

    assert [s.reps for s in repo.latest_progress_day("squat")] == [15, 10]
    assert repo.latest_progress_day("deadlift") == []


def test_progress_shows_on_session_summaries_and_can_be_updated_and_removed(
    repo: SqliteSessionRepository,
) -> None:
    session_id = saved_session(repo, D1, 12, 40.0)
    repo.save_progress(session_id, ProgressEntry(10, None))  # update

    [summary] = repo.list_sessions()
    assert summary.progress == ProgressEntry(10, None)
    stored = repo.get_session(session_id)
    assert stored is not None and stored.summary.progress == ProgressEntry(10, None)

    repo.remove_progress(session_id)
    assert repo.list_progress_sets("squat") == []
    assert repo.list_sessions()[0].progress is None


def test_saving_progress_for_an_unknown_session_fails(repo: SqliteSessionRepository) -> None:
    with pytest.raises(PersistenceError):
        repo.save_progress(999, ProgressEntry(10))


def test_deleting_a_session_removes_it_from_progress(repo: SqliteSessionRepository) -> None:
    session_id = saved_session(repo, D1, 12, 40.0)
    repo.delete_session(session_id)
    assert repo.list_progress_sets("squat") == []


V1_SCHEMA = """
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, exercise_key TEXT NOT NULL,
    exercise_name TEXT NOT NULL, started_at TEXT NOT NULL, ended_at TEXT
);
CREATE TABLE reps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    rep_number INTEGER NOT NULL, recorded_at TEXT NOT NULL, duration_ms INTEGER NOT NULL,
    feature_ranges TEXT NOT NULL, UNIQUE (session_id, rep_number)
);
CREATE TABLE violations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rep_id INTEGER NOT NULL REFERENCES reps(id) ON DELETE CASCADE,
    rule_id TEXT NOT NULL, message TEXT NOT NULL, explanation TEXT NOT NULL,
    measured REAL NOT NULL, limit_value REAL NOT NULL, timestamp_ms INTEGER NOT NULL,
    landmarks TEXT NOT NULL, snapshot_key TEXT
);
PRAGMA user_version = 1;
"""


def test_a_version_1_database_is_upgraded_and_keeps_its_sessions(tmp_path: Path) -> None:
    path = tmp_path / "history.db"
    connection = sqlite3.connect(path)
    connection.executescript(V1_SCHEMA)
    connection.execute(
        "INSERT INTO sessions (exercise_key, exercise_name, started_at)"
        " VALUES ('squat', 'Squat', '2026-10-01T10:00:00')"
    )
    connection.commit()
    connection.close()

    repo = SqliteSessionRepository(path, FileSnapshotStore(tmp_path / "snapshots"))
    [old] = repo.list_sessions()
    assert old.exercise_key == "squat" and old.progress is None

    repo.save_progress(old.session_id, ProgressEntry(12, 40.0))
    assert [s.reps for s in repo.list_progress_sets("squat")] == [12]
    repo.close()

    check = sqlite3.connect(path)
    assert check.execute("PRAGMA user_version").fetchone()[0] == 2
    check.close()