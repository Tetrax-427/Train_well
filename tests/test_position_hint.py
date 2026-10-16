from __future__ import annotations

from pose_tracker.application.exercise_analyzer import AnalysisStatus
from pose_tracker.application.position_hint import position_hint, view_hint
from pose_tracker.domain.exercises.squat import build_squat
from pose_tracker.domain.view import CameraView

SQUAT = build_squat()


def status(view: CameraView, view_ok: bool, value: float | None = None) -> AnalysisStatus:
    return AnalysisStatus(view, view_ok, value, 0, None)


def test_wrong_view_says_how_to_turn() -> None:
    assert view_hint(SQUAT, status(CameraView.FRONT, False)) == "Turn sideways to the camera"


def test_lost_body_says_to_step_back() -> None:
    hint = view_hint(SQUAT, status(CameraView.UNKNOWN, False))
    assert hint == "Step back so your full body is in frame"


def test_good_view_needs_no_view_hint() -> None:
    assert view_hint(SQUAT, status(CameraView.SIDE, True)) is None


def test_unmeasurable_driver_falls_back_to_the_exercise_hint() -> None:
    assert position_hint(SQUAT, status(CameraView.SIDE, True)) == SQUAT.position_hint


def test_measurable_exercise_needs_no_hint() -> None:
    assert position_hint(SQUAT, status(CameraView.SIDE, True, 150.0)) is None