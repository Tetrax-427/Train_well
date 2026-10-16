from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from pose_tracker.application.training_presenter import LiveState

_FEEDBACK_STYLES = {True: "color: #3fb950;", False: "color: #f85149;", None: ""}


class LivePanel(QFrame):
    """Read-only readout of the live session state."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("panel")
        self.setFixedWidth(300)
        self._feedback_good: bool | None = None

        self._exercise = self._label("title", wrap=True)
        self._view = self._label("caption")
        self._reps = self._label("bigNumber", "0")
        self._angle = self._label("number", "--")
        self._feedback_title = self._label("subtitle")
        self._feedback = self._label("", wrap=True)
        self._feedback.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        layout = QVBoxLayout(self)
        layout.addWidget(self._exercise)
        layout.addWidget(self._view)
        layout.addSpacing(12)
        layout.addWidget(self._label("caption", "REPS"))
        layout.addWidget(self._reps)
        layout.addWidget(self._label("caption", "ANGLE"))
        layout.addWidget(self._angle)
        layout.addSpacing(12)
        layout.addWidget(self._feedback_title)
        layout.addWidget(self._feedback, 1)

    def show_state(self, state: LiveState) -> None:
        self._exercise.setText(state.exercise_name or "No exercise selected")
        self._view.setText(state.view_text)
        self._reps.setText(str(state.rep_count))
        self._angle.setText(state.angle_text)
        self._feedback_title.setText(state.last_rep_title)
        self._feedback.setText("\n".join(f"• {line}" for line in state.feedback))
        if state.feedback_good != self._feedback_good:  # restyle only on change
            self._feedback_good = state.feedback_good
            self._feedback.setStyleSheet(_FEEDBACK_STYLES[state.feedback_good])

    @staticmethod
    def _label(name: str, text: str = "", wrap: bool = False) -> QLabel:
        label = QLabel(text)
        if name:
            label.setObjectName(name)
        label.setWordWrap(wrap)
        return label