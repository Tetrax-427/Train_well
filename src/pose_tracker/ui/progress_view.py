from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from pose_tracker.application.progress_presenter import ProgressPresenter
from pose_tracker.errors import PersistenceError
from pose_tracker.ui.progress_charts import ProgressCharts

_DEFAULT_RANGE_DAYS = 30


class ProgressView(QWidget):
    """The Progress tab: reps and weight per set, and volume per day, for saved sets only."""

    def __init__(self, presenter: ProgressPresenter) -> None:
        super().__init__()
        self._presenter = presenter

        self._exercise = QComboBox()
        for key, name in presenter.exercise_options():
            self._exercise.addItem(name, key)
        self._range = QComboBox()
        for days, label in presenter.range_options():
            self._range.addItem(label, days)
        self._range.setCurrentIndex(max(self._range.findData(_DEFAULT_RANGE_DAYS), 0))
        self._exercise.currentIndexChanged.connect(lambda _index: self.refresh())
        self._range.currentIndexChanged.connect(lambda _index: self.refresh())

        self._summary = QLabel()
        self._summary.setObjectName("caption")
        self._charts = ProgressCharts()
        self._placeholder = QLabel()
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setWordWrap(True)
        self._pages = QStackedWidget()
        self._pages.addWidget(self._placeholder)
        self._pages.addWidget(self._charts)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Exercise"))
        controls.addWidget(self._exercise)
        controls.addSpacing(16)
        controls.addWidget(QLabel("Range"))
        controls.addWidget(self._range)
        controls.addStretch(1)
        controls.addWidget(self._summary)

        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(self._pages, 1)

    def refresh(self) -> None:
        try:
            data = self._presenter.chart(self._exercise.currentData(), self._range.currentData())
        except PersistenceError as exc:
            QMessageBox.critical(self, "Progress unavailable", str(exc))
            return
        if not data.days:
            self._summary.setText("")
            self._placeholder.setText(
                f"No saved {self._exercise.currentText()} sets in this range.\n"
                "Finish a session and press Save to progress on its summary."
            )
            self._pages.setCurrentWidget(self._placeholder)
            return
        self._summary.setText(data.summary_text)
        self._charts.show_data(data)
        self._pages.setCurrentWidget(self._charts)