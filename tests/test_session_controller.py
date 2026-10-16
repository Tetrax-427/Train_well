from __future__ import annotations

import pytest
from pose_factory import squat_pose

from pose_tracker.application.exercise_analyzer import AnalysisStatus
from pose_tracker.application.session_controller import SessionController, SessionPhase
from pose_tracker.domain.exercises.push_up import build_push_up
from pose_tracker.domain.exercises.squat import build_squat
from pose_tracker.domain.view import CameraView, StableViewDetector, ViewDetector
from pose_tracker.errors import SessionStateError

STANDING = [175] * 3
DESCENT = list(range(170, 85, -5))
ASCENT = list(range(90, 176, 5))


class FakeRecorder:
    def __init__(self) -> None:
        self.recorded: list[object] = []
        self.closed = False
        self.session_id: int | None = None

    def record(self, exercise: object, result: object) -> None:
        self.recorded.append(result)
        self.session_id = 42

    def close(self) -> None:
        self.closed = True


def make_controller() -> tuple[SessionController, list[FakeRecorder]]:
    recorders: list[FakeRecorder] = []

    def new_recorder() -> FakeRecorder:
        recorders.append(FakeRecorder())
        return recorders[-1]

    controller = SessionController(
        {"squat": build_squat(), "push_up": build_push_up()},
        view_detector_factory=lambda: StableViewDetector(ViewDetector(), frames_to_switch=1),
        recorder_factory=new_recorder,
    )
    return controller, recorders


def feed_squat(controller: SessionController, knees: list[int]) -> AnalysisStatus | None:
    status = None
    for i, knee in enumerate(knees):
        status = controller.process(squat_pose(knee), i * 100, 1.0)
    return status


def test_starts_in_select_and_ignores_frames() -> None:
    controller, _ = make_controller()
    assert controller.phase is SessionPhase.SELECT
    assert controller.process(squat_pose(170), 0, 1.0) is None


def test_ready_previews_the_view_without_counting() -> None:
    controller, recorders = make_controller()
    controller.select("squat")
    status = feed_squat(controller, STANDING + DESCENT + ASCENT)
    assert controller.phase is SessionPhase.READY
    assert status is not None
    assert status.view is CameraView.SIDE and status.view_ok
    assert status.rep_count == 0
    assert recorders == []


def test_full_session_produces_a_report() -> None:
    controller, recorders = make_controller()
    controller.select("squat")
    controller.start()
    feed_squat(controller, STANDING + DESCENT + ASCENT)
    report = controller.stop()

    assert controller.phase is SessionPhase.SUMMARY
    assert controller.report is report
    assert report.exercise.key == "squat"
    assert (report.total_reps, report.clean_reps) == (1, 1)
    assert report.session_id == 42
    assert recorders[0].closed and len(recorders[0].recorded) == 1


def test_exercise_can_be_switched_after_a_session() -> None:
    controller, recorders = make_controller()
    controller.select("squat")
    controller.start()
    controller.stop()

    controller.select("push_up")
    assert controller.phase is SessionPhase.READY
    assert controller.report is None
    controller.start()

    assert controller.exercise is not None and controller.exercise.key == "push_up"
    assert len(recorders) == 2  # a fresh recorder (and so a fresh history session) per start


def test_exercise_cannot_change_mid_session() -> None:
    controller, _ = make_controller()
    controller.select("squat")
    controller.start()
    with pytest.raises(SessionStateError):
        controller.select("push_up")


def test_transitions_are_enforced() -> None:
    controller, _ = make_controller()
    with pytest.raises(SessionStateError):
        controller.start()
    with pytest.raises(SessionStateError):
        controller.stop()
    with pytest.raises(SessionStateError):
        controller.back()
    controller.select("squat")
    with pytest.raises(SessionStateError):
        controller.stop()


def test_unknown_exercise_is_rejected() -> None:
    controller, _ = make_controller()
    with pytest.raises(ValueError):
        controller.select("curl")


def test_back_returns_to_select_from_ready_and_summary() -> None:
    controller, _ = make_controller()
    controller.select("squat")
    controller.back()
    assert controller.phase is SessionPhase.SELECT and controller.exercise is None

    controller.select("squat")
    controller.start()
    controller.stop()
    controller.back()
    assert controller.phase is SessionPhase.SELECT and controller.report is None


def test_close_finalizes_a_running_session_only() -> None:
    controller, recorders = make_controller()
    controller.close()  # nothing running: no-op
    controller.select("squat")
    controller.start()
    controller.close()
    assert controller.phase is SessionPhase.SUMMARY
    assert recorders[0].closed