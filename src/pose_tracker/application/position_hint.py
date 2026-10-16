from __future__ import annotations

from pose_tracker.application.exercise_analyzer import AnalysisStatus
from pose_tracker.domain.exercise import Exercise
from pose_tracker.domain.view import CameraView

_VIEW_HINTS = {
    CameraView.SIDE: "Turn sideways to the camera",
    CameraView.FRONT: "Face the camera",
}


def view_hint(exercise: Exercise, status: AnalysisStatus) -> str | None:
    """What to change about where you stand, or None if the camera view is fine."""
    if status.view_ok:
        return None
    if status.view is CameraView.UNKNOWN:
        return "Step back so your full body is in frame"
    return _VIEW_HINTS.get(exercise.required_view, "Adjust your position")


def position_hint(exercise: Exercise, status: AnalysisStatus) -> str | None:
    """Like view_hint, but also reports when the view is fine yet the exercise can't be measured."""
    hint = view_hint(exercise, status)
    if hint is not None:
        return hint
    if status.driver_value is None:
        return exercise.position_hint
    return None