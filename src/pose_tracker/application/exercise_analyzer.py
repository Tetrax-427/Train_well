from __future__ import annotations

from dataclasses import dataclass

from typing import Protocol
from pose_tracker.domain import pose
from pose_tracker.domain.body_side import BodySide, select_visible_side
from pose_tracker.domain.exercise import Exercise
from pose_tracker.domain.features import compute_features
from pose_tracker.domain.form import FormViolation
from pose_tracker.domain.pose import Pose
from pose_tracker.domain.rep import Rep, RepDetector, Sample
from pose_tracker.domain.view import CameraView, StableViewDetector


@dataclass(frozen=True, slots=True)
class RepResult:
    rep_number: int
    rep: Rep
    violations: tuple[FormViolation, ...]

    @property
    def is_clean(self) -> bool:
        return not self.violations


@dataclass(frozen=True, slots=True)
class AnalysisStatus:
    view: CameraView
    view_ok: bool
    driver_value: float | None
    rep_count: int
    last_result: RepResult | None
    rep_elapsed_ms: int | None = None  # time into the current rep or hold


class RepRecorder(Protocol):
    def record(self, exercise: Exercise, result: RepResult) -> None: ...

    def close(self) -> None: ...

class ExerciseAnalyzer:
    """Runs one exercise: view gating -> features -> rep detection -> form rules."""

    def __init__(
        self,
        exercise: Exercise,
        view_detector: StableViewDetector,
        min_visibility: float = 0.5,
        recorder: RepRecorder | None = None,
    ) -> None:
        self._exercise = exercise
        self._view_detector = view_detector
        self._min_visibility = min_visibility
        self._recorder = recorder
        self._rep_detector = RepDetector(
            exercise.thresholds,
            min_duration_ms=exercise.min_rep_ms,
            lead_in_ms=exercise.lead_in_ms,
        )
        self._last_seen_ms = 0
        self._side = BodySide.LEFT
        self._results: list[RepResult] = []

    @property
    def exercise(self) -> Exercise:
        return self._exercise

    @property
    def results(self) -> tuple[RepResult, ...]:
        return tuple(self._results)

    def update(
        self, pose: Pose | None, timestamp_ms: int, aspect_ratio: float
    ) -> AnalysisStatus:
        view = self._view_detector.update(pose, aspect_ratio)

        if pose is None:
            lost_for = timestamp_ms - self._last_seen_ms
            if self._rep_detector.in_rep and lost_for < self._exercise.pose_grace_ms:
                return self._status(view, view_ok=True, value=None)  # brief dropout: keep the rep
            self._rep_detector.reset()
            return self._status(view, view_ok=False, value=None)
        self._last_seen_ms = timestamp_ms

        in_rep = self._rep_detector.in_rep
        # Mid-rep, posture changes can distort the view estimate; only gate between reps.
        if not in_rep and view is not self._exercise.required_view:
            self._rep_detector.reset()
            return self._status(view, view_ok=False, value=None)

        if not in_rep:
            self._side = select_visible_side(pose)  # locked for the duration of a rep

        features = compute_features(pose, self._side, aspect_ratio, self._min_visibility)
        value = self._exercise.driver(features)
        if value is None:
            return self._status(view, view_ok=True, value=None)

        rep = self._rep_detector.update(Sample(timestamp_ms, pose, features), value)
        if rep is not None:
            result = self._evaluate(rep)
            self._results.append(result)
            if self._recorder is not None:
                self._recorder.record(self._exercise, result)
        return self._status(view, view_ok=True, value=value)

    def _evaluate(self, rep: Rep) -> RepResult:
        violations = tuple(
            v for rule in self._exercise.rules if (v := rule.evaluate(rep)) is not None
        )
        return RepResult(len(self._results) + 1, rep, violations)

    def _status(self, view: CameraView, view_ok: bool, value: float | None) -> AnalysisStatus:
        return AnalysisStatus(
            view=view,
            view_ok=view_ok,
            driver_value=value,
            rep_count=len(self._results),
            last_result=self._results[-1] if self._results else None,
            rep_elapsed_ms=self._rep_detector.elapsed_ms,
        )