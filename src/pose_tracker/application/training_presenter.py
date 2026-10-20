from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from pose_tracker.application.exercise_analyzer import AnalysisStatus
from pose_tracker.application.position_hint import position_hint, view_hint
from pose_tracker.application.session_controller import (
    SessionController,
    SessionPhase,
    SessionReport,
)
from pose_tracker.domain.exercise import Exercise
from pose_tracker.domain.frame import Frame
from pose_tracker.domain.pose import Pose
from pose_tracker.interfaces import FrameObserver, PoseRenderer
from collections.abc import Callable
from pose_tracker.errors import PersistenceError

@dataclass(frozen=True, slots=True)
class LiveState:
    """Everything the training screen shows, as plain data."""

    phase: SessionPhase
    exercise_key: str | None
    exercise_name: str
    view_text: str
    banner: str
    banner_warning: bool
    rep_count: int
    angle_text: str
    last_rep_title: str
    feedback: tuple[str, ...]
    feedback_good: bool | None  # True = clean rep, False = issues, None = no rep yet
    can_select: bool
    can_start: bool
    can_stop: bool
    last_time: str = ""
    timer_text: str = ""  # running hold time for timed exercises, otherwise empty

@dataclass(frozen=True, slots=True)
class LiveUpdate:
    image: np.ndarray  # BGR frame with the skeleton drawn, no text
    state: LiveState


class TrainingPresenter:
    """Drives the session controller from UI events and frames; holds no Qt code."""

    def __init__(
        self,
        controller: SessionController,
        frames: FrameObserver,
        renderer: PoseRenderer,
        last_time: Callable[[str], str | None] = lambda _key: None,
    ) -> None:
        self._controller = controller
        self._frames = frames
        self._renderer = renderer
        self._last_time = last_time
        self._last_time_text = ""
        self._status: AnalysisStatus | None = None
    
    @property
    def exercises(self) -> tuple[Exercise, ...]:
        return self._controller.exercises

    # -- user actions ----------------------------------------------------------------

    def select(self, key: str) -> LiveState:
        self._controller.select(key)
        self._status = None
        self._last_time_text = self._lookup_last_time(key)
        return self.state()

    def finish(self) -> LiveState:
        """Leave the summary and go back to choosing an exercise."""
        self._controller.back()
        self._status = None
        self._last_time_text = ""
        return self.state()

    def _lookup_last_time(self, key: str) -> str:
        try:
            return self._last_time(key) or ""
        except PersistenceError:
            return ""  # a missing hint must never get in the way of training
        
    def start(self) -> LiveState:
        self._controller.start()
        self._status = None
        return self.state()

    def stop(self) -> SessionReport:
        report = self._controller.stop()
        self._status = None
        return report

    def close(self) -> None:
        self._controller.close()

    # -- frames ----------------------------------------------------------------------

    def on_frame(self, frame: Frame, pose: Pose | None) -> LiveUpdate:
        if self._controller.phase is SessionPhase.ACTIVE:
            # Before analysis, so a rep that finishes on this frame can find its snapshot.
            self._frames.observe(frame)
        height, width = frame.image.shape[:2]
        self._status = self._controller.process(pose, frame.timestamp_ms, width / height)
        image = self._renderer.render(frame.image, pose, 0.0)
        return LiveUpdate(image, self.state())

    # -- state -----------------------------------------------------------------------

    def state(self) -> LiveState:
        phase = self._controller.phase
        exercise = self._controller.exercise
        status = self._status
        banner, warning = self._banner(phase, exercise, status)

        live = status if phase is SessionPhase.ACTIVE else None
        last = live.last_result if live is not None else None
        angle = live.driver_value if live is not None else None
        elapsed = live.rep_elapsed_ms if live is not None else None
        timer = _clock(elapsed or 0) if exercise is not None and exercise.timed else ""
        if last is None:
            title, feedback, good = "", (), None
        else:
            messages = tuple(v.message for v in last.violations)
            title, feedback, good = f"Rep {last.rep_number}", messages or ("Good form",), last.is_clean

        return LiveState(
            phase=phase,
            exercise_key=exercise.key if exercise is not None else None,
            exercise_name=exercise.name if exercise is not None else "",
            view_text=f"View: {status.view.name.capitalize()}" if status is not None else "",
            banner=banner,
            banner_warning=warning,
            rep_count=live.rep_count if live is not None else 0,
            angle_text=f"{angle:.0f}°" if angle is not None else "--",
            last_rep_title=title,
            feedback=feedback,
            feedback_good=good,
            can_select=phase is not SessionPhase.ACTIVE,
            can_start=phase is SessionPhase.READY,
            can_stop=phase is SessionPhase.ACTIVE,
            last_time=self._last_time_text,
            timer_text=timer,
        )

    @staticmethod
    def _banner(
        phase: SessionPhase, exercise: Exercise | None, status: AnalysisStatus | None
    ) -> tuple[str, bool]:
        if phase is SessionPhase.SELECT or exercise is None:
            return "Choose an exercise to begin", False
        if phase is SessionPhase.SUMMARY:
            return "Session complete", False
        if status is None:
            return "Looking for you…", False
        ready = phase is SessionPhase.READY
        hint = view_hint(exercise, status) if ready else position_hint(exercise, status)
        if hint is not None:
            return hint, True
        return ("Ready. Press Start when you are set" if ready else "Tracking"), False

def _clock(elapsed_ms: int) -> str:
    minutes, seconds = divmod(elapsed_ms // 1000, 60)
    return f"{minutes}:{seconds:02d}"