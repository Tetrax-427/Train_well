from __future__ import annotations

from contextlib import ExitStack

from pose_tracker.application.exercise_analyzer import RepRecorder, RepResult
from pose_tracker.application.session_controller import SessionRecorder
from pose_tracker.domain.exercise import Exercise


class CompositeRepRecorder:
    """Fans each rep out to several recorders; close always reaches every one."""

    def __init__(self, *recorders: RepRecorder) -> None:
        self._recorders = recorders

    def record(self, exercise: Exercise, result: RepResult) -> None:
        for recorder in self._recorders:
            recorder.record(exercise, result)

    def close(self) -> None:
        with ExitStack() as stack:
            for recorder in self._recorders:
                stack.callback(recorder.close)


class SessionRepRecorder:
    """Fans reps out to several recorders and reports the history session id of the primary one."""

    def __init__(self, primary: SessionRecorder, *others: RepRecorder) -> None:
        self._primary = primary
        self._all = CompositeRepRecorder(primary, *others)

    @property
    def session_id(self) -> int | None:
        return self._primary.session_id

    def record(self, exercise: Exercise, result: RepResult) -> None:
        self._all.record(exercise, result)

    def close(self) -> None:
        self._all.close()