from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from pose_tracker.application.history_presenter import HistoryPresenter
from pose_tracker.errors import PersistenceError
from pose_tracker.interfaces import SnapshotPainter
from pose_tracker.ui.session_detail_view import SessionDetailView


class HistoryView(QWidget):
    """The History tab: past sessions on the left, the selected one in detail on the right."""

    def __init__(self, presenter: HistoryPresenter, painter: SnapshotPainter) -> None:
        super().__init__()
        self._presenter = presenter

        self._filter = QComboBox()
        for key, name in presenter.filter_options():
            self._filter.addItem(name, key)
        self._filter.currentIndexChanged.connect(lambda _index: self.refresh())

        self._list = QListWidget()
        self._list.currentItemChanged.connect(lambda _current, _previous: self._show_selection())

        left = QVBoxLayout()
        left.addWidget(self._filter)
        left.addWidget(self._list, 1)
        left_host = QWidget()
        left_host.setLayout(left)
        left_host.setFixedWidth(300)

        self._placeholder = QLabel()
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setWordWrap(True)
        self._detail = SessionDetailView(painter)
        self._detail.delete_requested.connect(self._on_delete_requested)
        self._pages = QStackedWidget()
        self._pages.addWidget(self._placeholder)
        self._pages.addWidget(self._detail)

        layout = QHBoxLayout(self)
        layout.addWidget(left_host)
        layout.addWidget(self._pages, 1)

    def refresh(self) -> None:
        """Reload the session list (keeping the selection if it still exists)."""
        selected = self._selected_id()
        try:
            rows = self._presenter.sessions(self._filter.currentData())
        except PersistenceError as exc:
            self._fail(exc)
            return

        self._list.blockSignals(True)
        self._list.clear()
        for row in rows:
            item = QListWidgetItem(f"{row.title}\n{row.subtitle}")
            item.setData(Qt.ItemDataRole.UserRole, row.session_id)
            self._list.addItem(item)
            if row.session_id == selected:
                self._list.setCurrentItem(item)
        self._list.blockSignals(False)
        self._show_selection()

    def _selected_id(self) -> int | None:
        item = self._list.currentItem()
        return None if item is None else item.data(Qt.ItemDataRole.UserRole)

    def _show_selection(self) -> None:
        session_id = self._selected_id()
        if session_id is None:
            self._placeholder.setText(
                "No sessions yet.\nFinish a training session and it will appear here."
                if self._list.count() == 0
                else "Select a session to see its details."
            )
            self._pages.setCurrentWidget(self._placeholder)
            return
        try:
            detail = self._presenter.load(session_id)
        except PersistenceError as exc:
            self._fail(exc)
            return
        if detail is None:
            self._placeholder.setText("That session no longer exists.")
            self._pages.setCurrentWidget(self._placeholder)
            return
        self._detail.show_detail(detail)
        self._pages.setCurrentWidget(self._detail)

    def _on_delete_requested(self, session_id: int) -> None:
        answer = QMessageBox.question(
            self, "Delete session",
            "Delete this session and its snapshots? This cannot be undone.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._presenter.delete(session_id)
        except PersistenceError as exc:
            self._fail(exc)
            return
        self.refresh()

    def _fail(self, error: PersistenceError) -> None:
        QMessageBox.critical(self, "History unavailable", str(error))