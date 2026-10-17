from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from functools import partial
from pathlib import Path

from pose_tracker.domain.body_side import select_visible_side
from pose_tracker.domain.history import SessionSummary, StoredSession, StoredViolation
from pose_tracker.domain.pose import LandmarkId, Pose
from pose_tracker.domain.rule_joints import highlighted_landmarks
from pose_tracker.interfaces import GhostFactory, ReferenceProvider, SessionReader
_BASE_LANDMARKS = 33  # the model's own landmarks; derived ones (neck, ...) come after


@dataclass(frozen=True, slots=True)
class SessionRow:
    session_id: int
    title: str
    subtitle: str


@dataclass(frozen=True, slots=True)
class MistakeCardData:
    rep_number: int
    title: str
    meta: str
    measurement: str
    explanation: str
    snapshot_path: Path | None
    pose: Pose
    highlights: tuple[LandmarkId, ...]
    ghost: GhostFactory | None  # corrected pose for a given aspect ratio; None = not available


@dataclass(frozen=True, slots=True)
class RepRowData:
    rep_number: int
    duration_text: str
    result_text: str
    is_clean: bool


@dataclass(frozen=True, slots=True)
class SessionDetail:
    session_id: int
    title: str
    when_text: str
    stats_text: str
    mistakes: tuple[MistakeCardData, ...]
    reps: tuple[RepRowData, ...]


class HistoryPresenter:
    """Turns stored sessions into display data. Holds no Qt code."""

    def __init__(
        self,
        reader: SessionReader,
        exercise_names: Mapping[str, str],
        references: ReferenceProvider,
    ) -> None:
        self._reader = reader
        self._names = dict(exercise_names)
        self._references = references

    def filter_options(self) -> tuple[tuple[str | None, str], ...]:
        return ((None, "All exercises"), *self._names.items())

    def sessions(self, exercise_key: str | None = None) -> tuple[SessionRow, ...]:
        return tuple(_row(s) for s in self._reader.list_sessions(exercise_key))

    def load(self, session_id: int) -> SessionDetail | None:
        stored = self._reader.get_session(session_id)
        return None if stored is None else _detail(stored, self._references)
    
    def delete(self, session_id: int) -> None:
        self._reader.delete_session(session_id)


def _row(summary: SessionSummary) -> SessionRow:
    return SessionRow(
        session_id=summary.session_id,
        title=summary.exercise_name,
        subtitle=(
            f"{_when(summary)} · {_reps(summary.total_reps)} · {summary.clean_reps} clean"
        ),
    )


def _detail(stored: StoredSession, references: ReferenceProvider) -> SessionDetail:
    summary = stored.summary
    issues = summary.total_reps - summary.clean_reps
    percent = round(100 * summary.clean_reps / summary.total_reps) if summary.total_reps else 0
    parts = [
        _reps(summary.total_reps),
        f"{summary.clean_reps} clean",
        f"{issues} with issues",
        f"{percent}% clean",
    ]
    if summary.ended_at is not None:
        parts.append(_duration(summary.ended_at - summary.started_at))

    mistakes = tuple(
        _card(rep.rep_number, f"{rep.recorded_at:%H:%M:%S}", violation, references)
        for rep in stored.reps
        for violation in rep.violations
    )

    reps = tuple(
        RepRowData(
            rep_number=rep.rep_number,
            duration_text=f"{rep.duration_ms / 1000:.1f}s",
            result_text="Clean" if rep.is_clean else "; ".join(v.message for v in rep.violations),
            is_clean=rep.is_clean,
        )
        for rep in stored.reps
    )
    return SessionDetail(
        session_id=summary.session_id,
        title=summary.exercise_name,
        when_text=_when(summary),
        stats_text=" · ".join(parts),
        mistakes=mistakes,
        reps=reps,
    )


def _card(
    rep_number: int, time_text: str, violation: StoredViolation, references: ReferenceProvider
) -> MistakeCardData:
    ghost: GhostFactory | None = None
    if references.has_reference(violation.rule_id):
        # Called later with the snapshot's aspect ratio, which only the image knows.
        ghost = partial(
            references.corrected_pose, violation.rule_id, violation.pose, violation.limit
        )
    return MistakeCardData(
        rep_number=rep_number,
        title=violation.message,
        meta=f"Rep {rep_number} · {time_text}",
        measurement=_measurement(violation.measured, violation.limit),
        explanation=violation.explanation,
        snapshot_path=violation.snapshot_path,
        pose=violation.pose,
        highlights=_highlights(violation),
        ghost=ghost,
    )


def _highlights(violation: StoredViolation) -> tuple[LandmarkId, ...]:
    if len(violation.pose.landmarks) < _BASE_LANDMARKS:
        return ()
    return highlighted_landmarks(violation.rule_id, select_visible_side(violation.pose))


def _measurement(measured: float, limit: float) -> str:
    # A violation means the measured value sits on the wrong side of the limit,
    # so the direction of the requirement follows from comparing the two.
    direction = "less" if measured > limit else "more"
    return f"Measured {_fmt(measured)}, needed {_fmt(limit)} or {direction}"


def _fmt(value: float) -> str:
    return f"{value:.1f}" if abs(value) >= 10 else f"{value:.3f}"


def _when(summary: SessionSummary) -> str:
    return f"{summary.started_at:%d %b %Y, %H:%M}"


def _reps(count: int) -> str:
    return f"{count} rep" if count == 1 else f"{count} reps"


def _duration(delta: timedelta) -> str:
    seconds = max(int(delta.total_seconds()), 0)
    minutes, rest = divmod(seconds, 60)
    return f"{rest} s" if minutes == 0 else f"{minutes} min {rest:02d} s"