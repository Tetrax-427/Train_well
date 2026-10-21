from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from pose_tracker.application.routine_presenter import RoutinePresenter
from pose_tracker.domain.routine import MAX_NAME_LENGTH
from pose_tracker.errors import PersistenceError

_OK = "color: #3fb950;"
_ERROR = "color: #f85149;"
_MUTED = "color: #8b949e;"


class RoutinesView(QWidget):
    """The Routines tab: create, edit and delete named lists of exercises, such as Push day."""

    routines_changed = Signal()
    train_requested = Signal(int)

    def __init__(self, presenter: RoutinePresenter) -> None:
        super().__init__()
        self._presenter = presenter
        self._names = dict(presenter.exercise_options())
        self._routine_id: int | None = None  # None while editing a routine that is not saved yet
        self._keys: list[str] = []
        self._dirty = False

        # Left: the saved routines.
        self._routines = QListWidget()
        self._routines.currentItemChanged.connect(lambda _current, _previous: self._on_selected())
        new = QPushButton("New routine")
        new.setObjectName("primary")
        new.clicked.connect(self._on_new)
        left = QVBoxLayout()
        left.addWidget(self._routines, 1)
        left.addWidget(new)
        left_host = QWidget()
        left_host.setLayout(left)
        left_host.setFixedWidth(280)

        # Right: the editor.
        self._name = QLineEdit()
        self._name.setPlaceholderText("Routine name, for example Push day")
        self._name.setMaxLength(MAX_NAME_LENGTH)
        self._name.textEdited.connect(lambda _text: self._mark_unsaved())
        self._name.returnPressed.connect(self._on_save)
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Name"))
        name_row.addWidget(self._name, 1)

        self._exercises = QListWidget()
        self._exercises.currentRowChanged.connect(lambda _row: self._update_buttons())
        self._up = QPushButton("Move up")
        self._up.clicked.connect(lambda: self._move(-1))
        self._down = QPushButton("Move down")
        self._down.clicked.connect(lambda: self._move(1))
        self._remove = QPushButton("Remove")
        self._remove.clicked.connect(self._on_remove)
        side = QVBoxLayout()
        for button in (self._up, self._down, self._remove):
            side.addWidget(button)
        side.addStretch(1)
        exercise_row = QHBoxLayout()
        exercise_row.addWidget(self._exercises, 1)
        exercise_row.addLayout(side)

        self._choice = QComboBox()
        self._add = QPushButton("Add exercise")
        self._add.clicked.connect(self._on_add)
        add_row = QHBoxLayout()
        add_row.addWidget(self._choice, 1)
        add_row.addWidget(self._add)

        self._status = QLabel()
        self._status.setWordWrap(True)
        self._save = QPushButton("Save routine")
        self._save.setObjectName("primary")
        self._save.clicked.connect(self._on_save)
        self._train = QPushButton("Train this routine")
        self._train.clicked.connect(self._on_train)
        self._delete = QPushButton("Delete routine")
        self._delete.setObjectName("danger")
        self._delete.clicked.connect(self._on_delete)
        actions = QHBoxLayout()
        actions.addWidget(self._save)
        actions.addWidget(self._train)
        actions.addStretch(1)
        actions.addWidget(self._delete)

        editor = QWidget()
        editor_layout = QVBoxLayout(editor)
        editor_layout.addLayout(name_row)
        editor_layout.addWidget(self._caption("EXERCISES, IN ORDER"))
        editor_layout.addLayout(exercise_row, 1)
        editor_layout.addLayout(add_row)
        editor_layout.addWidget(self._status)
        editor_layout.addLayout(actions)

        placeholder = QLabel("Select a routine, or create a new one.")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pages = QStackedWidget()
        self._pages.addWidget(placeholder)
        self._pages.addWidget(editor)
        self._editor = editor

        layout = QHBoxLayout(self)
        layout.addWidget(left_host)
        layout.addWidget(self._pages, 1)
        self.refresh()

    def refresh(self, select: int | None = None) -> None:
        """Reload the routine list, selecting ``select`` if given."""
        try:
            rows = self._presenter.routines()
        except PersistenceError as exc:
            self._fail(exc)
            return
        self._routines.blockSignals(True)
        self._routines.clear()
        for row in rows:
            item = QListWidgetItem(f"{row.title}\n{row.subtitle}")
            item.setData(Qt.ItemDataRole.UserRole, row.routine_id)
            self._routines.addItem(item)
            if row.routine_id == select:
                self._routines.setCurrentItem(item)
        self._routines.blockSignals(False)

    # -- selecting and editing -------------------------------------------------------

    def _on_selected(self) -> None:
        item = self._routines.currentItem()
        if item is not None:
            self._load(item.data(Qt.ItemDataRole.UserRole))

    def _on_new(self) -> None:
        self._routines.blockSignals(True)
        self._routines.setCurrentRow(-1)
        self._routines.clearSelection()
        self._routines.blockSignals(False)
        self._edit(None, "", [])
        self._name.setFocus()

    def _load(self, routine_id: int) -> None:
        try:
            detail = self._presenter.load(routine_id)
        except PersistenceError as exc:
            self._fail(exc)
            return
        if detail is None:  # deleted elsewhere
            self.refresh()
            self._pages.setCurrentIndex(0)
            return
        self._edit(detail.routine_id, detail.name, [key for key, _ in detail.exercises])

    def _edit(self, routine_id: int | None, name: str, keys: list[str]) -> None:
        self._routine_id = routine_id
        self._keys = list(keys)
        self._dirty = False
        self._name.setText(name)
        self._set_status("", _MUTED)
        self._render_exercises()
        self._pages.setCurrentWidget(self._editor)

    def _render_exercises(self, select: int | None = None) -> None:
        self._exercises.clear()
        for position, key in enumerate(self._keys, start=1):
            self._exercises.addItem(f"{position}. {self._names.get(key, key)}")
        self._choice.clear()
        for key, name in self._presenter.exercise_options():
            if key not in self._keys:
                self._choice.addItem(name, key)
        self._add.setEnabled(self._choice.count() > 0)
        if select is not None:
            self._exercises.setCurrentRow(select)
        self._update_buttons()

    def _update_buttons(self) -> None:
        row = self._exercises.currentRow()
        self._remove.setEnabled(row >= 0)
        self._up.setEnabled(row > 0)
        self._down.setEnabled(0 <= row < len(self._keys) - 1)
        saved = self._routine_id is not None
        self._delete.setEnabled(saved)
        self._train.setEnabled(saved and not self._dirty)  # Train uses the saved version

    def _mark_unsaved(self) -> None:
        self._dirty = True
        self._set_status("Unsaved changes.", _MUTED)
        self._update_buttons()

    def _on_add(self) -> None:
        key = self._choice.currentData()
        if key is None:
            return
        self._keys.append(key)
        self._mark_unsaved()
        self._render_exercises(select=len(self._keys) - 1)

    def _on_remove(self) -> None:
        row = self._exercises.currentRow()
        if row < 0:
            return
        del self._keys[row]
        self._mark_unsaved()
        self._render_exercises(select=min(row, len(self._keys) - 1))

    def _move(self, step: int) -> None:
        row = self._exercises.currentRow()
        target = row + step
        if row < 0 or not 0 <= target < len(self._keys):
            return
        self._keys[row], self._keys[target] = self._keys[target], self._keys[row]
        self._mark_unsaved()
        self._render_exercises(select=target)

    # -- saving, deleting, training ----------------------------------------------------

    def _on_save(self) -> None:
        try:
            if self._routine_id is None:
                routine_id = self._presenter.create(self._name.text(), self._keys)
            else:
                routine_id = self._routine_id
                self._presenter.update(routine_id, self._name.text(), self._keys)
        except (ValueError, PersistenceError) as exc:
            self._set_status(str(exc), _ERROR)
            return
        self.refresh(select=routine_id)
        self._load(routine_id)  # shows the saved (cleaned) version
        self._set_status("Saved.", _OK)
        self.routines_changed.emit()

    def _on_delete(self) -> None:
        if self._routine_id is None:
            return
        answer = QMessageBox.question(
            self, "Delete routine",
            f"Delete '{self._name.text()}'? Your training history is not affected.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._presenter.delete(self._routine_id)
        except PersistenceError as exc:
            self._fail(exc)
            return
        self._routine_id = None
        self.refresh()
        self._pages.setCurrentIndex(0)
        self.routines_changed.emit()

    def _on_train(self) -> None:
        if self._routine_id is not None:
            self.train_requested.emit(self._routine_id)

    # -- helpers ---------------------------------------------------------------------

    def _set_status(self, text: str, style: str) -> None:
        self._status.setText(text)
        self._status.setStyleSheet(style)

    def _fail(self, error: PersistenceError) -> None:
        QMessageBox.critical(self, "Routines unavailable", str(error))

    @staticmethod
    def _caption(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("caption")
        return label