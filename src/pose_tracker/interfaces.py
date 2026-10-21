from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Protocol
from collections.abc import Callable, Collection, Sequence
import numpy as np

from pose_tracker.domain.frame import Frame
from pose_tracker.domain.history import RepRecord, SessionSummary, StoredSession
from pose_tracker.domain.pose import LandmarkId, Pose
from pose_tracker.domain.progress import ProgressEntry, ProgressSet
from pose_tracker.domain.routine import Routine

class FrameSource(Protocol):
    def read(self) -> Frame | None:
        """Return the next frame, or None when the source is exhausted/failed."""

    def close(self) -> None: ...


class PoseEstimator(Protocol):
    def estimate(self, frame: Frame) -> Pose | None:
        """Return the tracked person's pose, or None if nobody is detected."""

    def close(self) -> None: ...


class PoseAnalyzer(Protocol):
    def analyze(
        self, pose: Pose | None, timestamp_ms: int, aspect_ratio: float
    ) -> Sequence[str]:
        """Analyze the pose and return text lines to overlay on the frame."""


class PoseRenderer(Protocol):
    def render(
        self,
        image: np.ndarray,
        pose: Pose | None,
        fps: float,
        status_lines: Sequence[str] = (),
    ) -> np.ndarray:
        """Return a new image with the pose and status text drawn on it."""


class FrameDisplay(Protocol):
    def show(self, image: np.ndarray) -> bool:
        """Display the image. Return False when the user asked to stop."""

    def close(self) -> None: ...


class FrameObserver(Protocol):
    def observe(self, frame: Frame) -> None:
        """Called by the pipeline with every frame, before analysis."""


class FrameEncoder(Protocol):
    def encode(self, image: np.ndarray) -> bytes | None:
        """Return the image as JPEG bytes, or None if encoding failed."""


class SnapshotSource(Protocol):
    def nearest(self, timestamp_ms: int) -> bytes | None:
        """JPEG of the frame closest to the timestamp, or None if none is close enough."""


class SnapshotStore(Protocol):
    def save(self, session_id: int, name: str, jpeg: bytes) -> str:
        """Store the image and return its key."""

    def resolve(self, key: str) -> Path: ...

    def delete_session(self, session_id: int) -> None: ...


class SessionWriter(Protocol):
    def start_session(
        self, exercise_key: str, exercise_name: str, started_at: datetime
    ) -> int: ...

    def add_rep(self, session_id: int, rep: RepRecord) -> None: ...

    def finish_session(self, session_id: int, ended_at: datetime) -> None: ...


class SessionReader(Protocol):
    def list_sessions(self, exercise_key: str | None = None) -> list[SessionSummary]: ...

    def get_session(self, session_id: int) -> StoredSession | None: ...

    def delete_session(self, session_id: int) -> None: ...

GhostFactory = Callable[[float], Pose | None]  # image aspect ratio -> corrected pose


class ReferenceProvider(Protocol):
    def has_reference(self, rule_id: str) -> bool:
        """Whether mistakes of this rule can be shown against a corrected pose."""

    def corrected_pose(
        self, rule_id: str, pose: Pose, limit: float, aspect_ratio: float
    ) -> Pose | None:
        """Where the body should have been for the rule to pass, or None if unknown."""


class SnapshotPainter(Protocol):
    def paint(
        self,
        path: Path,
        pose: Pose,
        highlights: Collection[LandmarkId],
        overlay: bool,
        ghost: GhostFactory | None = None,
    ) -> np.ndarray | None:
        """The stored snapshot with the pose and/or the corrected pose drawn on it.

        ``ghost`` is called with the image's aspect ratio. None if the file is unreadable.
        """


class ProgressWriter(Protocol):
    def save_progress(self, session_id: int, entry: ProgressEntry) -> None:
        """Mark the session as saved to progress, or update its saved reps and weight."""

    def remove_progress(self, session_id: int) -> None: ...


class ProgressReader(Protocol):
    def list_progress_sets(
        self, exercise_key: str, since: datetime | None = None
    ) -> list[ProgressSet]:
        """Saved sets of one exercise from ``since`` on, oldest first."""

    def latest_progress_day(self, exercise_key: str) -> list[ProgressSet]:
        """All saved sets of the most recent day that has any, oldest first."""

class RoutineStore(Protocol):
    def list_routines(self) -> list[Routine]:
        """All routines, oldest first."""

    def get_routine(self, routine_id: int) -> Routine | None: ...

    def create_routine(self, name: str, exercise_keys: Sequence[str]) -> Routine:
        """Raises ValueError if the name is already taken."""

    def update_routine(self, routine_id: int, name: str, exercise_keys: Sequence[str]) -> None:
        """Raises ValueError if another routine has the name."""

    def delete_routine(self, routine_id: int) -> None: ...