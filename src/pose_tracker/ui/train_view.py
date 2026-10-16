from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from pose_tracker.application.session_controller import SessionPhase
from pose_tracker.application.session_summary import build_summary
from pose_tracker.application.training_presenter import LiveState, TrainingPresenter
from pose_tracker.errors import SessionStateError
from pose_tracker.ui.capture_thread import CapturedFrame, CaptureThread
from pose_tracker.ui.live_panel import LivePanel
from pose_tracker.ui.summary_view import SummaryView
from pose_tracker.ui.video_widget import VideoWidget

_BANNER_BASE = "border-radius: 8px; padding: 10px; font-size: 16px; font-weight: 600;"
_BANNER_NORMAL = f"background: #161b22; border: 1px solid #30363d; color: #e6edf3; {_BANNER_BASE}"
_BANNER_WARNING = f"background: #3b2300; border: 1px solid #9e6a03; color: #f0b72f; {_BANNER_BASE}"


class TrainView(QWidget):
    """The Train tab: exercise list, live video, live panel, session summary and controls."""

    exit_requested = Signal()

    def __init__(
        self, presenter: TrainingPresenter, capture: CaptureThread, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._presenter = presenter
        self._capture = capture
        self._camera_failed = False
        self._banner_warning: bool | None = None
        self._keys = [exercise.key for exercise in presenter.exercises]

        self._exercises = QListWidget()
        self._exercises.setFixedWidth(200)
        for exercise in presenter.exercises:
            item = QListWidgetItem(exercise.name)
            item.setData(Qt.ItemDataRole.UserRole, exercise.key)
            self._exercises.addItem(item)
        self._exercises.itemClicked.connect(self._on_exercise_clicked)

        self._video = VideoWidget()
        self._banner = QLabel()
        self._banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._banner.setWordWrap(True)
        self._panel = LivePanel()

        self._live_page = QWidget()
        video_column = QVBoxLayout()
        video_column.addWidget(self._video, 1)
        video_column.addWidget(self._banner)
        live_layout = QHBoxLayout(self._live_page)
        live_layout.addLayout(video_column, 1)
        live_layout.addWidget(self._panel)

        self._summary = SummaryView()
        self._summary.train_again.connect(self._on_train_again)
        self._summary.done.connect(self._on_done)

        self._pages = QStackedWidget()
        self._pages.addWidget(self._live_page)
        self._pages.addWidget(self._summary)

        self._start = QPushButton("Start")
        self._start.setObjectName("primary")
        self._start.clicked.connect(self._on_start)
        self._stop = QPushButton("Stop")
        self._stop.setObjectName("danger")
        self._stop.clicked.connect(self._stop_session)
        exit_button = QPushButton("Exit")
        exit_button.clicked.connect(self.exit_requested)

        bar = QHBoxLayout()
        bar.addWidget(self._start)
        bar.addWidget(self._stop)
        bar.addStretch(1)
        bar.addWidget(exit_button)

        body = QHBoxLayout()
        body.addWidget(self._exercises)
        body.addWidget(self._pages, 1)
        root = QVBoxLayout(self)
        root.addLayout(body, 1)
        root.addLayout(bar)

        capture.frame_ready.connect(self._on_frame)
        capture.stopped.connect(self._on_capture_stopped)
        self._apply(presenter.state())

    # -- lifecycle -------------------------------------------------------------------

    def start_capture(self) -> None:
        self._capture.start()

    def confirm_close(self) -> bool:
        if not self._presenter.state().can_stop:
            return True
        answer = QMessageBox.question(
            self, "Session in progress", "A session is running. Stop it, save the reps and exit?"
        )
        return answer == QMessageBox.StandardButton.Yes

    def shutdown(self) -> None:
        """Stop the camera thread, then finalize any running session."""
        self._capture.request_stop()
        self._capture.wait(5000)
        self._presenter.close()

    # -- frames ----------------------------------------------------------------------

    def _on_frame(self, captured: CapturedFrame) -> None:
        try:
            update = self._presenter.on_frame(captured.frame, captured.pose)
            if self._pages.currentWidget() is self._live_page:
                self._video.show_image(update.image)
            self._apply(update.state)
        finally:
            self._capture.frame_consumed()

    def _on_capture_stopped(self, reason: str) -> None:
        if not reason:
            return
        self._camera_failed = True
        if self._presenter.state().can_stop:
            self._stop_session()  # keep the reps counted so far
        self._apply(self._presenter.state())
        QMessageBox.critical(self, "Camera stopped", reason)

    # -- user actions ----------------------------------------------------------------

    def _on_exercise_clicked(self, item: QListWidgetItem) -> None:
        key = item.data(Qt.ItemDataRole.UserRole)
        self._dispatch(lambda: self._presenter.select(key))

    def _on_start(self) -> None:
        self._dispatch(self._presenter.start)

    def _stop_session(self) -> None:
        def action() -> LiveState:
            report = self._presenter.stop()
            self._summary.show_summary(build_summary(report))
            return self._presenter.state()

        self._dispatch(action)

    def _on_train_again(self) -> None:
        key = self._presenter.state().exercise_key
        if key is not None:
            self._dispatch(lambda: self._presenter.select(key))

    def _on_done(self) -> None:
        self._dispatch(self._presenter.finish)

    def _dispatch(self, action: Callable[[], LiveState]) -> None:
        try:
            state = action()
        except SessionStateError as exc:
            QMessageBox.warning(self, "Not allowed right now", str(exc))
            return
        self._apply(state)

    # -- rendering -------------------------------------------------------------------

    def _apply(self, state: LiveState) -> None:
        self._panel.show_state(state)
        self._banner.setText(state.banner)
        if state.banner_warning != self._banner_warning:  # restyle only on change
            self._banner_warning = state.banner_warning
            self._banner.setStyleSheet(_BANNER_WARNING if state.banner_warning else _BANNER_NORMAL)

        self._exercises.setEnabled(state.can_select)
        self._start.setEnabled(state.can_start and not self._camera_failed)
        self._stop.setEnabled(state.can_stop)

        row = self._keys.index(state.exercise_key) if state.exercise_key in self._keys else -1
        if self._exercises.currentRow() != row:
            self._exercises.setCurrentRow(row)

        page = self._summary if state.phase is SessionPhase.SUMMARY else self._live_page
        if self._pages.currentWidget() is not page:
            self._pages.setCurrentWidget(page)