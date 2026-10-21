from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
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

from pose_tracker.application.progress_presenter import ProgressPresenter
from pose_tracker.application.routine_presenter import RoutinePresenter
from pose_tracker.application.session_controller import SessionPhase
from pose_tracker.application.session_summary import build_summary
from pose_tracker.application.training_presenter import LiveState, TrainingPresenter
from pose_tracker.errors import PersistenceError, SessionStateError
from pose_tracker.ui.capture_thread import CapturedFrame, CaptureThread
from pose_tracker.ui.live_panel import LivePanel
from pose_tracker.ui.summary_view import SummaryView
from pose_tracker.ui.video_widget import VideoWidget

_BANNER_BASE = "border-radius: 8px; padding: 10px; font-size: 16px; font-weight: 600;"
_BANNER_NORMAL = f"background: #161b22; border: 1px solid #30363d; color: #e6edf3; {_BANNER_BASE}"
_BANNER_WARNING = f"background: #3b2300; border: 1px solid #9e6a03; color: #f0b72f; {_BANNER_BASE}"


class TrainView(QWidget):
    """The Train tab: routine and exercise lists, live video, live panel, summary and controls."""

    def __init__(
        self,
        presenter: TrainingPresenter,
        capture: CaptureThread,
        progress: ProgressPresenter,
        routines: RoutinePresenter,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._presenter = presenter
        self._capture = capture
        self._routines = routines
        self._camera_failed = False
        self._banner_warning: bool | None = None
        self._keys: list[str] = []

        caption = QLabel("ROUTINE")
        caption.setObjectName("caption")
        self._routine = QComboBox()
        self._routine.currentIndexChanged.connect(lambda _index: self._fill_exercises())
        self._exercises = QListWidget()
        self._exercises.itemClicked.connect(self._on_exercise_clicked)
        picker = QVBoxLayout()
        picker.addWidget(caption)
        picker.addWidget(self._routine)
        picker.addWidget(self._exercises, 1)
        picker_host = QWidget()
        picker_host.setLayout(picker)
        picker_host.setFixedWidth(220)

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

        self._summary = SummaryView(progress)
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
        bar = QHBoxLayout()
        bar.addWidget(self._start)
        bar.addWidget(self._stop)
        bar.addStretch(1)

        body = QHBoxLayout()
        body.addWidget(picker_host)
        body.addWidget(self._pages, 1)
        root = QVBoxLayout(self)
        root.addLayout(body, 1)
        root.addLayout(bar)

        capture.frame_ready.connect(self._on_frame)
        capture.stopped.connect(self._on_capture_stopped)
        self.refresh_routines()  # fills the lists and shows the initial state

    # -- routines --------------------------------------------------------------------

    def refresh_routines(self) -> None:
        """Reload the routine choices, keeping the current one if it still exists."""
        current = self._routine.currentData()
        try:
            options = self._routines.routine_options()
        except PersistenceError:
            options = ((None, "All exercises"),)
        self._routine.blockSignals(True)
        self._routine.clear()
        for routine_id, name in options:
            self._routine.addItem(name, routine_id)
        self._routine.setCurrentIndex(max(self._routine.findData(current), 0))
        self._routine.blockSignals(False)
        self._fill_exercises()

    def show_routine(self, routine_id: int) -> None:
        """Show only this routine's exercises. Ignored while a set is running."""
        if not self._presenter.state().can_select:
            return
        self.refresh_routines()
        index = self._routine.findData(routine_id)
        if index >= 0:
            self._routine.setCurrentIndex(index)

    def _fill_exercises(self) -> None:
        try:
            options = self._routines.exercises_for(self._routine.currentData())
        except PersistenceError:
            options = self._routines.exercise_options()
        self._exercises.clear()
        for key, name in options:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self._exercises.addItem(item)
        self._keys = [key for key, _ in options]
        self._apply(self._presenter.state())  # restores the highlighted exercise

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

        self._routine.setEnabled(state.can_select)
        self._exercises.setEnabled(state.can_select)
        self._start.setEnabled(state.can_start and not self._camera_failed)
        self._stop.setEnabled(state.can_stop)

        row = self._keys.index(state.exercise_key) if state.exercise_key in self._keys else -1
        if self._exercises.currentRow() != row:
            self._exercises.setCurrentRow(row)

        page = self._summary if state.phase is SessionPhase.SUMMARY else self._live_page
        if self._pages.currentWidget() is not page:
            self._pages.setCurrentWidget(page)