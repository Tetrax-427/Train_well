from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

from pose_tracker.domain.routine import Routine
from pose_tracker.errors import PersistenceError

_SCHEMA_VERSION = 1

_SCHEMA = f"""
CREATE TABLE routines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE
);
CREATE TABLE routine_exercises (
    routine_id INTEGER NOT NULL REFERENCES routines(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    exercise_key TEXT NOT NULL,
    PRIMARY KEY (routine_id, position),
    UNIQUE (routine_id, exercise_key)
);
PRAGMA user_version = {_SCHEMA_VERSION};
"""


class SqliteRoutineRepository:
    """Routines in their own SQLite file. Used from the UI thread only."""

    def __init__(self, db_path: Path) -> None:
        try:
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(db_path)
        except (OSError, sqlite3.Error) as exc:
            raise PersistenceError(f"Cannot open the routines database at {db_path}") from exc
        try:
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._migrate()
        except sqlite3.Error as exc:
            self._conn.close()
            raise PersistenceError(f"Cannot initialize the routines database at {db_path}") from exc
        except PersistenceError:
            self._conn.close()
            raise

    def list_routines(self) -> list[Routine]:
        with self._db() as db:
            routines = db.execute("SELECT id, name FROM routines ORDER BY id").fetchall()
            items = db.execute(
                "SELECT routine_id, exercise_key FROM routine_exercises"
                " ORDER BY routine_id, position"
            ).fetchall()
        keys: dict[int, list[str]] = {}
        for row in items:
            keys.setdefault(row["routine_id"], []).append(row["exercise_key"])
        return [
            Routine(row["id"], row["name"], tuple(keys.get(row["id"], ()))) for row in routines
        ]

    def get_routine(self, routine_id: int) -> Routine | None:
        with self._db() as db:
            row = db.execute(
                "SELECT id, name FROM routines WHERE id = ?", (routine_id,)
            ).fetchone()
            if row is None:
                return None
            items = db.execute(
                "SELECT exercise_key FROM routine_exercises WHERE routine_id = ?"
                " ORDER BY position",
                (routine_id,),
            ).fetchall()
        return Routine(row["id"], row["name"], tuple(item["exercise_key"] for item in items))

    def create_routine(self, name: str, exercise_keys: Sequence[str]) -> Routine:
        with self._db() as db:
            self._require_free_name(db, name, own_id=None)
            cursor = db.execute("INSERT INTO routines (name) VALUES (?)", (name,))
            routine_id = _require_id(cursor.lastrowid)
            self._write_exercises(db, routine_id, exercise_keys)
        return Routine(routine_id, name, tuple(exercise_keys))

    def update_routine(self, routine_id: int, name: str, exercise_keys: Sequence[str]) -> None:
        with self._db() as db:
            exists = db.execute("SELECT 1 FROM routines WHERE id = ?", (routine_id,)).fetchone()
            if exists is None:
                raise PersistenceError(f"Routine {routine_id} no longer exists")
            self._require_free_name(db, name, own_id=routine_id)
            db.execute("UPDATE routines SET name = ? WHERE id = ?", (name, routine_id))
            db.execute("DELETE FROM routine_exercises WHERE routine_id = ?", (routine_id,))
            self._write_exercises(db, routine_id, exercise_keys)

    def delete_routine(self, routine_id: int) -> None:
        with self._db() as db:
            db.execute("DELETE FROM routines WHERE id = ?", (routine_id,))

    def close(self) -> None:
        self._conn.close()

    # -- internals -------------------------------------------------------------------

    def _migrate(self) -> None:
        version = self._conn.execute("PRAGMA user_version").fetchone()[0]
        if version > _SCHEMA_VERSION:
            raise PersistenceError(
                f"Routines database is version {version}; this app supports up to {_SCHEMA_VERSION}"
            )
        if version == 0:
            self._conn.executescript(_SCHEMA)

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        try:
            with self._conn:  # commits on success, rolls back on any error
                yield self._conn
        except sqlite3.Error as exc:
            raise PersistenceError("Routines database operation failed") from exc

    @staticmethod
    def _require_free_name(db: sqlite3.Connection, name: str, own_id: int | None) -> None:
        row = db.execute("SELECT id FROM routines WHERE name = ? COLLATE NOCASE", (name,)).fetchone()
        if row is not None and row["id"] != own_id:
            raise ValueError(f"A routine named '{name}' already exists.")

    @staticmethod
    def _write_exercises(
        db: sqlite3.Connection, routine_id: int, exercise_keys: Sequence[str]
    ) -> None:
        db.executemany(
            "INSERT INTO routine_exercises (routine_id, position, exercise_key) VALUES (?, ?, ?)",
            [(routine_id, position, key) for position, key in enumerate(exercise_keys)],
        )


def _require_id(row_id: int | None) -> int:
    if row_id is None:
        raise PersistenceError("Database did not return a row id")
    return row_id