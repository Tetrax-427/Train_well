from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pose_tracker.application.progress_presenter import ProgressPresenter
from pose_tracker.application.session_summary import MistakeTally, SummaryState
from pose_tracker.ui.progress_save_box import ProgressSaveBox
from pose_tracker.ui.qt_helpers import clear_layout


class SummaryView(QWidget):
    """End-of-session report: totals, save-to-progress, mistakes with explanations, every rep."""

    train_again = Signal()
    done = Signal()

    def __init__(self, progress: ProgressPresenter) -> None:
        super().__init__()
        self._title = QLabel()
        self._title.setObjectName("title")
        self._stats = QLabel()
        self._save_box = ProgressSaveBox(progress)

        self._mistakes = QVBoxLayout()
        host = QWidget()
        host.setLayout(self._mistakes)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(host)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Rep", "Time", "Result"])
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)

        again = QPushButton("Train again")
        again.setObjectName("primary")
        again.clicked.connect(self.train_again)
        other = QPushButton("Choose another exercise")
        other.clicked.connect(self.done)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(other)
        buttons.addWidget(again)

        layout = QVBoxLayout(self)
        layout.addWidget(self._title)
        layout.addWidget(self._stats)
        layout.addWidget(self._save_box)
        layout.addWidget(self._section("MISTAKES TO FIX"))
        layout.addWidget(scroll, 3)
        layout.addWidget(self._section("EVERY REP"))
        layout.addWidget(self._table, 2)
        layout.addLayout(buttons)

    def show_summary(self, summary: SummaryState) -> None:
        self._title.setText(f"{summary.exercise_name}: session summary")
        self._stats.setText(
            f"{summary.total_reps} reps  ·  {summary.clean_reps} clean  ·  "
            f"{summary.issue_reps} with issues  ·  {summary.clean_percent}% clean"
        )
        if summary.session_id is None:
            self._save_box.bind_unavailable(
                "This session was not stored in history, so it can't be added to progress."
            )
        elif summary.total_reps == 0:
            self._save_box.bind_unavailable("No reps were counted, so there is nothing to save.")
        else:
            self._save_box.bind(summary.session_id, summary.exercise_key, summary.total_reps, None)
        self._fill_mistakes(summary)
        self._fill_rows(summary)

    def _fill_mistakes(self, summary: SummaryState) -> None:
        clear_layout(self._mistakes)
        if not summary.mistakes:
            text = "No reps recorded." if summary.total_reps == 0 else "No form mistakes. Great session!"
            self._mistakes.addWidget(QLabel(text))
        for tally in summary.mistakes:
            self._mistakes.addWidget(self._card(tally))
        self._mistakes.addStretch(1)

    def _fill_rows(self, summary: SummaryState) -> None:
        self._table.setRowCount(len(summary.rows))
        for index, row in enumerate(summary.rows):
            result = "Clean" if row.is_clean else "; ".join(row.issues)
            for column, text in enumerate((str(row.rep_number), f"{row.duration_s:.1f}s", result)):
                self._table.setItem(index, column, QTableWidgetItem(text))
        self._table.resizeColumnsToContents()

    @staticmethod
    def _card(tally: MistakeTally) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)

        title = QLabel(tally.message)
        title.setObjectName("cardTitle")
        title.setWordWrap(True)
        layout.addWidget(title)

        reps = ", ".join(str(n) for n in tally.rep_numbers)
        noun = "rep" if tally.count == 1 else "reps"
        meta = QLabel(f"Seen in {tally.count} {noun}: {reps}")
        meta.setObjectName("caption")
        layout.addWidget(meta)

        if tally.explanation:
            why = QLabel(tally.explanation)
            why.setWordWrap(True)
            why.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(why)
        return card

    @staticmethod
    def _section(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("caption")
        return label