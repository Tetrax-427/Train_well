from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pose_tracker.domain.pose import Pose


@dataclass(frozen=True, slots=True)
class ViolationRecord:
    """A form mistake ready to be persisted."""

    rule_id: str
    message: str
    explanation: str
    measured: float
    limit: float
    timestamp_ms: int
    pose: Pose
    snapshot_jpeg: bytes | None


@dataclass(frozen=True, slots=True)
class RepRecord:
    rep_number: int
    recorded_at: datetime
    duration_ms: int
    feature_ranges: Mapping[str, tuple[float, float]]
    violations: tuple[ViolationRecord, ...]


@dataclass(frozen=True, slots=True)
class StoredViolation:
    rule_id: str
    message: str
    explanation: str
    measured: float
    limit: float
    timestamp_ms: int
    pose: Pose
    snapshot_path: Path | None  # None if no snapshot was saved or the file is gone


@dataclass(frozen=True, slots=True)
class StoredRep:
    rep_number: int
    recorded_at: datetime
    duration_ms: int
    feature_ranges: Mapping[str, tuple[float, float]]
    violations: tuple[StoredViolation, ...]

    @property
    def is_clean(self) -> bool:
        return not self.violations


@dataclass(frozen=True, slots=True)
class SessionSummary:
    session_id: int
    exercise_key: str
    exercise_name: str
    started_at: datetime
    ended_at: datetime | None
    total_reps: int
    clean_reps: int


@dataclass(frozen=True, slots=True)
class StoredSession:
    summary: SessionSummary
    reps: tuple[StoredRep, ...]