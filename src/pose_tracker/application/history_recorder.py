from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime

from pose_tracker.application.exercise_analyzer import RepResult
from pose_tracker.domain.exercise import Exercise
from pose_tracker.domain.history import RepRecord, ViolationRecord
from pose_tracker.domain.rep_stats import feature_ranges
from pose_tracker.errors import PersistenceError
from pose_tracker.interfaces import SessionWriter, SnapshotSource

logger = logging.getLogger(__name__)


class HistoryRepRecorder:
    """Persists each finished rep, with snapshots of its mistakes, as one history session.

    The session is created on the first rep (so empty sessions never appear in history)
    and finished on close. Persistence failures are logged, never raised.
    """

    def __init__(
        self,
        writer: SessionWriter,
        snapshots: SnapshotSource,
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._writer = writer
        self._snapshots = snapshots
        self._clock = clock
        self._started_at = clock()
        self._session_id: int | None = None
        self._closed = False

    @property
    def session_id(self) -> int | None:
        return self._session_id

    def record(self, exercise: Exercise, result: RepResult) -> None:
        try:
            if self._session_id is None:
                self._session_id = self._writer.start_session(
                    exercise.key, exercise.name, self._started_at
                )
            self._writer.add_rep(self._session_id, self._to_record(exercise, result))
        except PersistenceError:
            logger.exception("Could not save rep %d to history", result.rep_number)

    def close(self) -> None:
        if self._session_id is None or self._closed:
            return
        self._closed = True
        try:
            self._writer.finish_session(self._session_id, self._clock())
        except PersistenceError:
            logger.exception("Could not finalize the history session")

    def _to_record(self, exercise: Exercise, result: RepResult) -> RepRecord:
        violations = tuple(
            ViolationRecord(
                rule_id=v.rule_id,
                message=v.message,
                explanation=exercise.explanations.get(v.rule_id, ""),
                measured=v.measured,
                limit=v.limit,
                timestamp_ms=v.timestamp_ms,
                pose=v.pose,
                snapshot_jpeg=self._snapshots.nearest(v.timestamp_ms),
            )
            for v in result.violations
        )
        return RepRecord(
            rep_number=result.rep_number,
            recorded_at=self._clock(),
            duration_ms=result.rep.duration_ms,
            feature_ranges=feature_ranges(result.rep, exercise.logged_features),
            violations=violations,
        )