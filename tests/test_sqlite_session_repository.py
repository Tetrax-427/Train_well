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