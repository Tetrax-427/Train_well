from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pose_tracker.application.history_presenter import SessionDetail
from pose_tracker.interfaces import SnapshotPainter
from pose_tracker.ui.mistake_card import MistakeCard
from pose_tracker.ui.qt_helpers import clear_layout


class SessionDetailView(QWidget):
    """Totals, every mistake with its snapshot, and every rep of one stored session."""

    delete_requested = Signal(int)

    def __init__(self, painter: SnapshotPainter) -> None:
        super().__init__()
        self._painter = painter
        self._session_id: int | None = None
        self._cards: list[MistakeCard] = []

        self._title = QLabel()
        self._title.setObjectName("title")
        self._when = QLabel()
        self._when.setObjectName("caption")
        self._stats = QLabel()
        self._stats.setWordWrap(True)

        self._overlay = QCheckBox("Show my skeleton")
        self._overlay.setChecked(True)
        self._overlay.toggled.connect(self._on_display_toggled)
        self._ghost = QCheckBox("Show corrected pose")
        self._ghost.setChecked(True)
        self._ghost.toggled.connect(self._on_display_toggled)
        delete = QPushButton("Delete session")
        delete.setObjectName("danger")
        delete.clicked.connect(self._on_delete_clicked)

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

        header = QHBoxLayout()
        header.addWidget(self._overlay)
        header.addWidget(self._ghost)
        header.addStretch(1)
        header.addWidget(delete)

        layout = QVBoxLayout(self)
        layout.addWidget(self._title)
        layout.addWidget(self._when)
        layout.addWidget(self._stats)
        layout.addLayout(header)
        layout.addWidget(self._caption("MISTAKES"))
        layout.addWidget(scroll, 3)
        layout.addWidget(self._caption("EVERY REP"))
        layout.addWidget(self._table, 2)

    def show_detail(self, detail: SessionDetail) -> None:
        self._session_id = detail.session_id
        self._title.setText(detail.title)
        self._when.setText(detail.when_text)
        self._stats.setText(detail.stats_text)

        clear_layout(self._mistakes)
        self._cards = []
        if not detail.mistakes:
            text = "No reps recorded." if not detail.reps else "No form mistakes in this session."
            self._mistakes.addWidget(QLabel(text))
        for data in detail.mistakes:
            card = MistakeCard(
                data, self._painter, self._overlay.isChecked(), self._ghost.isChecked()
            )
            self._cards.append(card)
            self._mistakes.addWidget(card)
        self._mistakes.addStretch(1)

        self._table.setRowCount(len(detail.reps))
        for index, rep in enumerate(detail.reps):
            for column, text in enumerate((str(rep.rep_number), rep.duration_text, rep.result_text)):
                self._table.setItem(index, column, QTableWidgetItem(text))
        self._table.resizeColumnsToContents()

    def _on_display_toggled(self, _checked: bool) -> None:
        for card in self._cards:
            card.set_display(self._overlay.isChecked(), self._ghost.isChecked())

    def _on_delete_clicked(self) -> None:
        if self._session_id is not None:
            self.delete_requested.emit(self._session_id)

    @staticmethod
    def _caption(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("caption")
        return label