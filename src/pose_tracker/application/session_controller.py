from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum, auto
from typing import Protocol

from pose_tracker.application.exercise_analyzer import (
    AnalysisStatus,
    ExerciseAnalyzer,
    RepRecorder,
    RepResult,
)
from pose_tracker.domain.exercise import Exercise
from pose_tracker.domain.pose import Pose
from pose_tracker.domain.view import StableViewDetector
from pose_tracker.errors import SessionStateError


class SessionPhase(Enum):
    SELECT = auto()   # choosing an exercise
    READY = auto()    # exercise chosen; live view check, nothing counted yet
    ACTIVE = auto()   # reps are counted, checked and recorded
    SUMMARY = auto()  # session over; report available


class SessionRecorder(RepRecorder, Protocol):
    @property
    def session_id(self) -> int | None: ...


@dataclass(frozen=True, slots=True)
class SessionReport:
    exercise: Exercise
    results: tuple[RepResult, ...]
    session_id: int | None  # history id; None if nothing was persisted

    @property
    def total_reps(self) -> int:
        return len(self.results)

    @property
    def clean_reps(self) -> int:
        return sum(1 for result in self.results if result.is_clean)


class SessionController:
    """State machine for one training session at a time: select -> ready -> active -> summary."""

    def __init__(
        self,
        catalog: Mapping[str, Exercise],
        view_detector_factory: Callable[[], StableViewDetector],
        recorder_factory: Callable[[], SessionRecorder],
        min_visibility: float = 0.5,
    ) -> None:
        if not catalog:
            raise ValueError("catalog must contain at least one exercise")
        self._catalog = catalog
        self._view_detector_factory = view_detector_factory
        self._recorder_factory = recorder_factory
        self._min_visibility = min_visibility
        self._phase = SessionPhase.SELECT
        self._exercise: Exercise | None = None
        self._view_detector: StableViewDetector | None = None
        self._analyzer: ExerciseAnalyzer | None = None
        self._recorder: SessionRecorder | None = None
        self._report: SessionReport | None = None

    @property
    def phase(self) -> SessionPhase:
        return self._phase

    @property
    def exercises(self) -> tuple[Exercise, ...]:
        return tuple(self._catalog.values())

    @property
    def exercise(self) -> Exercise | None:
        return self._exercise

    @property
    def report(self) -> SessionReport | None:
        return self._report

    def select(self, key: str) -> None:
        """Choose (or change) the exercise. Not allowed mid-session."""
        if self._phase is SessionPhase.ACTIVE:
            raise SessionStateError("Stop the current session before choosing another exercise")
        try:
            exercise = self._catalog[key]
        except KeyError:
            raise ValueError(f"Unknown exercise: {key!r}") from None
        self._exercise = exercise
        self._view_detector = self._view_detector_factory()
        self._report = None
        self._phase = SessionPhase.READY

    def start(self) -> None:
        self._require(SessionPhase.READY, "start")
        assert self._exercise is not None and self._view_detector is not None
        self._recorder = self._recorder_factory()
        self._analyzer = ExerciseAnalyzer(
            self._exercise, self._view_detector, self._min_visibility, self._recorder
        )
        self._phase = SessionPhase.ACTIVE

    def stop(self) -> SessionReport:
        self._require(SessionPhase.ACTIVE, "stop")
        assert self._exercise is not None
        assert self._analyzer is not None and self._recorder is not None
        analyzer, recorder = self._analyzer, self._recorder
        self._analyzer = self._recorder = None
        self._phase = SessionPhase.SUMMARY
        recorder.close()
        self._report = SessionReport(self._exercise, analyzer.results, recorder.session_id)
        return self._report

    def back(self) -> None:
        """Return to exercise selection from READY or SUMMARY."""
        if self._phase not in (SessionPhase.READY, SessionPhase.SUMMARY):
            raise SessionStateError(f"Cannot go back from {self._phase.name}")
        self._exercise = self._view_detector = self._report = None
        self._phase = SessionPhase.SELECT

    def process(
        self, pose: Pose | None, timestamp_ms: int, aspect_ratio: float
    ) -> AnalysisStatus | None:
        """Feed one frame. Returns live status in READY and ACTIVE, None otherwise."""
        if self._phase is SessionPhase.ACTIVE:
            assert self._analyzer is not None
            return self._analyzer.update(pose, timestamp_ms, aspect_ratio)
        if self._phase is SessionPhase.READY:
            assert self._exercise is not None and self._view_detector is not None
            view = self._view_detector.update(pose, aspect_ratio)
            return AnalysisStatus(
                view=view,
                view_ok=view is self._exercise.required_view,
                driver_value=None,
                rep_count=0,
                last_result=None,
            )
        return None

    def close(self) -> None:
        """Call on app exit: finalizes a session that is still running."""
        if self._phase is SessionPhase.ACTIVE:
            self.stop()

    def _require(self, phase: SessionPhase, action: str) -> None:
        if self._phase is not phase:
            raise SessionStateError(
                f"Cannot {action} while {self._phase.name}; {phase.name} is required"
            )