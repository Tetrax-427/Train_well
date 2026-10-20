from __future__ import annotations

import numpy as np
from pose_factory import squat_pose

from pose_tracker.application.session_controller import SessionController, SessionPhase
from pose_tracker.application.training_presenter import LiveUpdate, TrainingPresenter
from pose_tracker.domain.exercises.push_up import build_push_up
from pose_tracker.domain.exercises.squat import build_squat
from pose_tracker.domain.frame import Frame
from pose_tracker.domain.view import StableViewDetector, ViewDetector
from collections.abc import Callable  
from pose_tracker.errors import PersistenceError
from pose_factory import plank_pose, press_pose
from pose_tracker.domain.exercises.plank import build_plank

STANDING = [175] * 3
DESCENT = list(range(170, 85, -5))
ASCENT = list(range(90, 176, 5))
SHALLOW = list(range(170, 125, -5)) + list(range(130, 176, 5))


class FakeRecorder:
    def __init__(self) -> None:
        self.session_id: int | None = None

    def record(self, exercise: object, result: object) -> None:
        self.session_id = 1

    def close(self) -> None: ...


class FakeRenderer:
    def __init__(self) -> None:
        self.output = np.ones((8, 8, 3), dtype=np.uint8)
        self.calls = 0

    def render(self, image, pose, fps, status_lines=()):
        self.calls += 1
        return self.output


class FakeFrames:
    def __init__(self) -> None:
        self.seen = 0

    def observe(self, frame: Frame) -> None:
        self.seen += 1


def make_presenter(
    last_time: Callable[[str], str | None] = lambda _key: None,
) -> tuple[TrainingPresenter, FakeRenderer, FakeFrames]:
    controller = SessionController(
        {"squat": build_squat(), "push_up": build_push_up()},
        view_detector_factory=lambda: StableViewDetector(ViewDetector(), frames_to_switch=1),
        recorder_factory=FakeRecorder,
    )
    renderer, frames = FakeRenderer(), FakeFrames()
    return TrainingPresenter(controller, frames, renderer, last_time), renderer, frames

def feed(presenter: TrainingPresenter, knees: list[int], gap: float = 0.0) -> LiveUpdate:
    update = None
    for i, knee in enumerate(knees):
        frame = Frame(np.zeros((8, 8, 3), dtype=np.uint8), i * 100)
        update = presenter.on_frame(frame, squat_pose(knee, shoulder_gap=gap))
    assert update is not None
    return update


def test_initial_state_asks_for_an_exercise() -> None:
    presenter, _, _ = make_presenter()
    state = presenter.state()
    assert state.phase is SessionPhase.SELECT
    assert state.banner == "Choose an exercise to begin"
    assert state.can_select and not state.can_start and not state.can_stop


def test_selecting_an_exercise_enables_start_and_reports_when_the_position_is_good() -> None:
    presenter, _, _ = make_presenter()
    presenter.select("squat")
    state = feed(presenter, [175]).state
    assert state.phase is SessionPhase.READY and state.can_start
    assert state.banner == "Ready. Press Start when you are set" and not state.banner_warning
    assert state.view_text == "View: Side"


def test_wrong_view_shows_a_warning() -> None:
    presenter, _, _ = make_presenter()
    presenter.select("squat")
    state = feed(presenter, [175], gap=0.3).state
    assert state.banner == "Turn sideways to the camera" and state.banner_warning


def test_active_session_counts_reps_and_reports_good_form() -> None:
    presenter, _, _ = make_presenter()
    presenter.select("squat")
    presenter.start()
    state = feed(presenter, STANDING + DESCENT + ASCENT).state

    assert state.phase is SessionPhase.ACTIVE
    assert state.can_stop and not state.can_select and not state.can_start
    assert state.rep_count == 1
    assert state.last_rep_title == "Rep 1"
    assert state.feedback == ("Good form",) and state.feedback_good is True
    assert state.angle_text.endswith("°")
    assert state.banner == "Tracking"


def test_flawed_rep_lists_the_mistake() -> None:
    presenter, _, _ = make_presenter()
    presenter.select("squat")
    presenter.start()
    state = feed(presenter, STANDING + SHALLOW).state
    assert state.feedback_good is False
    assert any("Go deeper" in line for line in state.feedback)


def test_frames_are_only_buffered_while_a_session_is_active() -> None:
    presenter, _, frames = make_presenter()
    presenter.select("squat")
    feed(presenter, STANDING)
    assert frames.seen == 0
    presenter.start()
    feed(presenter, STANDING)
    assert frames.seen == 3


def test_every_frame_is_rendered_and_the_rendered_image_is_returned() -> None:
    presenter, renderer, _ = make_presenter()
    update = feed(presenter, STANDING)  # even with no exercise selected
    assert renderer.calls == 3
    assert update.image is renderer.output


def test_stopping_gives_a_report_and_allows_switching_exercise() -> None:
    presenter, _, _ = make_presenter()
    presenter.select("squat")
    presenter.start()
    feed(presenter, STANDING + DESCENT + ASCENT)
    report = presenter.stop()

    state = presenter.state()
    assert report.total_reps == 1
    assert state.phase is SessionPhase.SUMMARY and state.banner == "Session complete"
    assert state.can_select and not state.can_stop

    assert presenter.select("push_up").exercise_name == "Push-up"
    assert presenter.state().phase is SessionPhase.READY


def test_finish_returns_to_selection() -> None:
    presenter, _, _ = make_presenter()
    presenter.select("squat")
    presenter.start()
    presenter.stop()
    state = presenter.finish()
    assert state.phase is SessionPhase.SELECT and state.exercise_key is None

def test_selecting_an_exercise_shows_what_you_did_last_time() -> None:
    presenter, _, _ = make_presenter(lambda key: f"Last time: {key}")
    assert presenter.state().last_time == ""
    assert presenter.select("squat").last_time == "Last time: squat"
    presenter.start()
    presenter.stop()
    assert presenter.finish().last_time == ""


def test_no_saved_history_means_no_hint() -> None:
    presenter, _, _ = make_presenter(lambda _key: None)
    assert presenter.select("squat").last_time == ""


def test_a_failing_lookup_never_blocks_selecting_an_exercise() -> None:
    def failing(_key: str) -> str | None:
        raise PersistenceError("db down")

    presenter, _, _ = make_presenter(failing)
    state = presenter.select("squat")
    assert state.exercise_key == "squat" and state.last_time == ""

def test_timed_exercises_show_a_running_hold_timer() -> None:
    controller = SessionController(
        {"plank": build_plank(), "squat": build_squat()},
        view_detector_factory=lambda: StableViewDetector(ViewDetector(), frames_to_switch=1),
        recorder_factory=FakeRecorder,
    )
    presenter = TrainingPresenter(controller, FakeFrames(), FakeRenderer())
    assert presenter.select("squat").timer_text == ""

    assert presenter.select("plank").timer_text == "0:00"
    presenter.start()
    update = None
    for i, pose in enumerate([press_pose(120)] * 3 + [plank_pose()] * 20):
        update = presenter.on_frame(Frame(np.zeros((8, 8, 3), dtype=np.uint8), i * 100), pose)
    assert update is not None and update.state.timer_text == "0:01"