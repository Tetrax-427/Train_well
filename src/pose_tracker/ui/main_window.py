from __future__ import annotations

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow, QTabWidget

from pose_tracker.ui.history_view import HistoryView
from pose_tracker.ui.progress_view import ProgressView
from pose_tracker.ui.train_view import TrainView


class MainWindow(QMainWindow):
    def __init__(
        self,
        title: str,
        train_view: TrainView,
        history_view: HistoryView,
        progress_view: ProgressView,
    ) -> None:
        super().__init__()
        self.setWindowTitle(title)
        self.resize(1280, 760)
        self._train = train_view
        self._history = history_view
        self._progress = progress_view

        self._tabs = QTabWidget()
        self._tabs.addTab(train_view, "Train")
        self._tabs.addTab(history_view, "History")
        self._tabs.addTab(progress_view, "Progress")
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(self._tabs)

        train_view.exit_requested.connect(self.close)
        history_view.refresh()

    def start_capture(self) -> None:
        self._train.start_capture()

    def _on_tab_changed(self, index: int) -> None:
        widget = self._tabs.widget(index)
        if widget is self._history:
            self._history.refresh()  # picks up sessions saved since the last visit
        elif widget is self._progress:
            self._progress.refresh()

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._train.confirm_close():
            event.ignore()
            return
        self._train.shutdown()
        event.accept()