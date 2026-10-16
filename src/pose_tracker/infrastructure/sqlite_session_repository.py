from __future__ import annotations

import json
import logging
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from pose_tracker.domain.history import (
    RepRecord,
    SessionSummary,
    StoredRep,
    StoredSession,
    StoredViolation,
    ViolationRecord,
)
from pose_tracker.domain.pose import Landmark, Pose
from pose_tracker.errors import PersistenceError
from pose_tracker.interfaces import SnapshotStore

logger = logging.getLogger(__name__)

_SCHEMA_VERSION = 1

_SCHEMA = f"""
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exercise_key TEXT NOT NULL,
    exercise_name TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT
);
CREATE TABLE reps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    rep_number INTEGER NOT NULL,
    recorded_at TEXT NOT NULL,
    duration_ms INTEGER NOT NULL,
    feature_ranges TEXT NOT NULL,
    UNIQUE (session_id, rep_number)
);
CREATE TABLE violations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rep_id INTEGER NOT NULL REFERENCES reps(id) ON DELETE CASCADE,
    rule_id TEXT NOT NULL,
    message TEXT NOT NULL,
    explanation TEXT NOT NULL,
    measured REAL NOT NULL,
    limit_value REAL NOT NULL,
    timestamp_ms INTEGER NOT NULL,
    landmarks TEXT NOT NULL,
    snapshot_key TEXT
);
CREATE INDEX idx_sessions_started ON sessions(started_at);
CREATE INDEX idx_reps_session ON reps(session_id);
CREATE INDEX idx_violations_rep ON violations(rep_id);
PRAGMA user_version = {_SCHEMA_VERSION};
"""

# A rep is clean when it has no violations; counts are derived, never stored.
_SUMMARY_SQL = """
SELECT s.id, s.exercise_key, s.exercise_name, s.started_at, s.ended_at,
       (SELECT COUNT(*) FROM reps r WHERE r.session_id = s.id) AS total_reps,
       (SELECT COUNT(*) FROM reps r WHERE r.session_id = s.id
          AND NOT EXISTS (SELECT 1 FROM violations v WHERE v.rep_id = r.id)) AS clean_reps
FROM sessions s
"""


class SqliteSessionRepository:
    """Implements SessionWriter and SessionReader on SQLite, with snapshots in a SnapshotStore.

    One connection shared across threads (the camera loop writes, the UI reads), so
    every operation is serialized by a lock.
    """

    def __init__(self, db_path: Path, snapshots: SnapshotStore) -> None:
        self._snapshots = snapshots
        self._lock = threading.RLock()
        try:
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(db_path, check_same_thread=False)
        except (OSError, sqlite3.Error) as exc:
            raise PersistenceError(f"Cannot open history database at {db_path}") from exc
        try:
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._migrate()
        except sqlite3.Error as exc:
            self._conn.close()
            raise PersistenceError(f"Cannot initialize history database at {db_path}") from exc
        except PersistenceError:
            self._conn.close()
            raise

    # -- SessionWriter ---------------------------------------------------------------

    def start_session(self, exercise_key: str, exercise_name: str, started_at: datetime) -> int:
        with self._db() as db:
            cursor = db.execute(
                "INSERT INTO sessions (exercise_key, exercise_name, started_at) VALUES (?, ?, ?)",
                (exercise_key, exercise_name, _iso(started_at)),
            )
            return _require_id(cursor.lastrowid)

    def add_rep(self, session_id: int, rep: RepRecord) -> None:
        keys = [self._save_snapshot(session_id, rep.rep_number, v) for v in rep.violations]
        ranges = {name: [low, high] for name, (low, high) in rep.feature_ranges.items()}
        with self._db() as db:
            cursor = db.execute(
                "INSERT INTO reps (session_id, rep_number, recorded_at, duration_ms, feature_ranges)"
                " VALUES (?, ?, ?, ?, ?)",
                (session_id, rep.rep_number, _iso(rep.recorded_at), rep.duration_ms,
                 json.dumps(ranges)),
            )
            rep_id = _require_id(cursor.lastrowid)
            db.executemany(
                "INSERT INTO violations (rep_id, rule_id, message, explanation, measured,"
                " limit_value, timestamp_ms, landmarks, snapshot_key)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (rep_id, v.rule_id, v.message, v.explanation, v.measured, v.limit,
                     v.timestamp_ms, _encode_pose(v.pose), key)
                    for v, key in zip(rep.violations, keys, strict=True)
                ],
            )

    def finish_session(self, session_id: int, ended_at: datetime) -> None:
        with self._db() as db:
            db.execute(
                "UPDATE sessions SET ended_at = ? WHERE id = ?", (_iso(ended_at), session_id)
            )

    # -- SessionReader ---------------------------------------------------------------

    def list_sessions(self, exercise_key: str | None = None) -> list[SessionSummary]:
        sql = _SUMMARY_SQL
        params: tuple[str, ...] = ()
        if exercise_key is not None:
            sql += " WHERE s.exercise_key = ?"
            params = (exercise_key,)
        sql += " ORDER BY s.started_at DESC, s.id DESC"
        with self._db() as db:
            rows = db.execute(sql, params).fetchall()
        return [_summary(row) for row in rows]

    def get_session(self, session_id: int) -> StoredSession | None:
        with self._db() as db:
            summary_row = db.execute(_SUMMARY_SQL + " WHERE s.id = ?", (session_id,)).fetchone()
            if summary_row is None:
                return None
            rep_rows = db.execute(
                "SELECT id, rep_number, recorded_at, duration_ms, feature_ranges"
                " FROM reps WHERE session_id = ? ORDER BY rep_number",
                (session_id,),
            ).fetchall()
            violation_rows = db.execute(
                "SELECT v.* FROM violations v JOIN reps r ON r.id = v.rep_id"
                " WHERE r.session_id = ? ORDER BY v.id",
                (session_id,),
            ).fetchall()

        by_rep: dict[int, list[StoredViolation]] = {}
        for row in violation_rows:
            by_rep.setdefault(row["rep_id"], []).append(self._stored_violation(row))
        reps = tuple(
            StoredRep(
                rep_number=row["rep_number"],
                recorded_at=datetime.fromisoformat(row["recorded_at"]),
                duration_ms=row["duration_ms"],
                feature_ranges={
                    name: (low, high)
                    for name, (low, high) in json.loads(row["feature_ranges"]).items()
                },
                violations=tuple(by_rep.get(row["id"], ())),
            )
            for row in rep_rows
        )
        return StoredSession(_summary(summary_row), reps)

    def delete_session(self, session_id: int) -> None:
        with self._db() as db:
            db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        self._snapshots.delete_session(session_id)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # -- internals -------------------------------------------------------------------

    def _migrate(self) -> None:
        version = self._conn.execute("PRAGMA user_version").fetchone()[0]
        if version == 0:
            self._conn.executescript(_SCHEMA)
        elif version > _SCHEMA_VERSION:
            raise PersistenceError(
                f"History database is version {version}; this app supports up to {_SCHEMA_VERSION}"
            )

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            try:
                with self._conn:  # commits on success, rolls back on error
                    yield self._conn
            except sqlite3.Error as exc:
                raise PersistenceError("History database operation failed") from exc

    def _save_snapshot(
        self, session_id: int, rep_number: int, violation: ViolationRecord
    ) -> str | None:
        if violation.snapshot_jpeg is None:
            return None
        try:
            return self._snapshots.save(
                session_id, f"rep{rep_number}_{violation.rule_id}", violation.snapshot_jpeg
            )
        except (OSError, ValueError):
            logger.exception("Could not save the snapshot for %s", violation.rule_id)
            return None

    def _stored_violation(self, row: sqlite3.Row) -> StoredViolation:
        return StoredViolation(
            rule_id=row["rule_id"],
            message=row["message"],
            explanation=row["explanation"],
            measured=row["measured"],
            limit=row["limit_value"],
            timestamp_ms=row["timestamp_ms"],
            pose=_decode_pose(row["landmarks"]),
            snapshot_path=self._existing_snapshot(row["snapshot_key"]),
        )

    def _existing_snapshot(self, key: str | None) -> Path | None:
        if key is None:
            return None
        try:
            path = self._snapshots.resolve(key)
        except ValueError:
            return None
        return path if path.is_file() else None


def _iso(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds")


def _require_id(row_id: int | None) -> int:
    if row_id is None:
        raise PersistenceError("Database did not return a row id")
    return row_id


def _summary(row: sqlite3.Row) -> SessionSummary:
    return SessionSummary(
        session_id=row["id"],
        exercise_key=row["exercise_key"],
        exercise_name=row["exercise_name"],
        started_at=datetime.fromisoformat(row["started_at"]),
        ended_at=datetime.fromisoformat(row["ended_at"]) if row["ended_at"] else None,
        total_reps=row["total_reps"],
        clean_reps=row["clean_reps"],
    )


def _encode_pose(pose: Pose) -> str:
    return json.dumps(
        [[round(lm.x, 4), round(lm.y, 4), round(lm.z, 4), round(lm.visibility, 3)]
         for lm in pose.landmarks],
        separators=(",", ":"),
    )


def _decode_pose(text: str) -> Pose:
    return Pose(tuple(Landmark(x, y, z, v) for x, y, z, v in json.loads(text)))