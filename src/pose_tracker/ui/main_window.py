from __future__ import annotations

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow, QTabWidget

from pose_tracker.ui.train_view import TrainView


class MainWindow(QMainWindow):
    """Hosts the tabs. The History tab (step 4) is added next to Train."""

    def __init__(self, title: str, train_view: TrainView) -> None:
        super().__init__()
        self.setWindowTitle(title)
        self.resize(1280, 760)
        self._train = train_view
        tabs = QTabWidget()
        tabs.addTab(train_view, "Train")
        self.setCentralWidget(tabs)
        train_view.exit_requested.connect(self.close)

    def start_capture(self) -> None:
        self._train.start_capture()

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._train.confirm_close():
            event.ignore()
            return
        self._train.shutdown()
        event.accept()