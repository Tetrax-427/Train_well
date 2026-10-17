from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from pose_tracker.application.progress_presenter import ProgressPresenter
from pose_tracker.domain.progress import MAX_REPS, ProgressEntry, describe_entry
from pose_tracker.errors import PersistenceError

_OK = "color: #3fb950;"
_ERROR = "color: #f85149;"
_MUTED = "color: #8b949e;"


class ProgressSaveBox(QFrame):
    """Save a session to Progress as one set (weight and reps), update it, or remove it."""

    changed = Signal()

    def __init__(self, presenter: ProgressPresenter) -> None:
        super().__init__()
        self.setObjectName("card")
        self._presenter = presenter
        self._session_id: int | None = None

        caption = QLabel("PROGRESS")
        caption.setObjectName("caption")
        self._hint = QLabel()
        self._hint.setWordWrap(True)
        self._weight = QLineEdit()
        self._weight.setPlaceholderText("kg (empty = bodyweight)")
        self._weight.setMaximumWidth(220)
        self._weight.returnPressed.connect(self._on_save)
        self._reps = QSpinBox()
        self._reps.setRange(1, MAX_REPS)
        self._save = QPushButton("Save to progress")
        self._save.setObjectName("primary")
        self._save.clicked.connect(self._on_save)
        self._remove = QPushButton("Remove from progress")
        self._remove.clicked.connect(self._on_remove)
        self._status = QLabel()
        self._status.setWordWrap(True)

        row = QHBoxLayout()
        row.addWidget(QLabel("Weight (kg)"))
        row.addWidget(self._weight)
        row.addWidget(QLabel("Reps"))
        row.addWidget(self._reps)
        row.addWidget(self._save)
        row.addWidget(self._remove)
        row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(caption)
        layout.addWidget(self._hint)
        layout.addLayout(row)
        layout.addWidget(self._status)

    def bind(
        self, session_id: int, exercise_key: str, detected_reps: int, entry: ProgressEntry | None
    ) -> None:
        self._session_id = session_id
        self._set_enabled(True)
        self._hint.setText(self._last_time(exercise_key))
        if entry is None:
            self._weight.clear()
            self._reps.setValue(min(max(detected_reps, 1), MAX_REPS))
            self._show_saved(False)
            self._set_status("", _MUTED)
        else:
            self._weight.setText("" if entry.weight_kg is None else f"{entry.weight_kg:g}")
            self._reps.setValue(entry.reps)
            self._show_saved(True)
            self._set_status(f"In Progress: {describe_entry(entry)}", _OK)

    def bind_unavailable(self, message: str) -> None:
        self._session_id = None
        self._set_enabled(False)
        self._hint.setText("")
        self._show_saved(False)
        self._set_status(message, _MUTED)

    def _on_save(self) -> None:
        if self._session_id is None:
            return
        try:
            text = self._presenter.save(self._session_id, self._weight.text(), self._reps.value())
        except (ValueError, PersistenceError) as exc:
            self._set_status(str(exc), _ERROR)
            return
        self._show_saved(True)
        self._set_status(f"Saved to progress: {text}", _OK)
        self.changed.emit()

    def _on_remove(self) -> None:
        if self._session_id is None:
            return
        try:
            self._presenter.remove(self._session_id)
        except PersistenceError as exc:
            self._set_status(str(exc), _ERROR)
            return
        self._show_saved(False)
        self._set_status("Removed from progress.", _MUTED)
        self.changed.emit()

    def _last_time(self, exercise_key: str) -> str:
        try:
            return self._presenter.last_time(exercise_key) or "No saved sets for this exercise yet."
        except PersistenceError:
            return ""

    def _show_saved(self, saved: bool) -> None:
        self._save.setText("Update" if saved else "Save to progress")
        self._remove.setVisible(saved)

    def _set_enabled(self, enabled: bool) -> None:
        for widget in (self._weight, self._reps, self._save, self._remove):
            widget.setEnabled(enabled)

    def _set_status(self, text: str, style: str) -> None:
        self._status.setText(text)
        self._status.setStyleSheet(style)