from __future__ import annotations

import logging
import threading

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from pose_tracker.application.chat.agent import ChatAgent
from pose_tracker.domain.chat import ChatAnswer
from pose_tracker.errors import PoseTrackerError

logger = logging.getLogger(__name__)

_SUGGESTIONS = (
    "Review my training this week",
    "Which form mistakes do I make most?",
    "Is my bench press progressing?",
    "Plan a push day for me",
)
_EMPTY_HTML = (
    "<p style='color:#8b949e'>Ask about your training: what you did, which mistakes keep "
    "coming up, how your lifts are progressing, or ask for a plan.</p>"
)


class _Bridge(QObject):
    """Carries results from the worker thread to the UI thread."""

    progress = Signal(str)
    answered = Signal(object)
    failed = Signal(str)


class ChatView(QWidget):
    """The Chat tab: ask a language model about your training. It looks your data up with tools."""

    def __init__(self, agent: ChatAgent, model_label: str) -> None:
        super().__init__()
        self._agent = agent
        self._entries: list[tuple[str, str]] = []  # (kind, text): user, assistant or error
        self._busy = False
        self._last_question = ""

        self._bridge = _Bridge()
        self._bridge.progress.connect(self._on_progress)
        self._bridge.answered.connect(self._on_answered)
        self._bridge.failed.connect(self._on_failed)

        title = QLabel("Coach")
        title.setObjectName("title")
        model = QLabel(model_label)
        model.setObjectName("caption")
        self._new = QPushButton("New chat")
        self._new.clicked.connect(self._on_new_chat)
        header = QHBoxLayout()
        header.addWidget(title)
        header.addWidget(model)
        header.addStretch(1)
        header.addWidget(self._new)

        self._transcript = QTextBrowser()
        self._transcript.setOpenLinks(False)

        self._suggestions: list[QPushButton] = []
        suggestion_row = QHBoxLayout()
        for text in _SUGGESTIONS:
            button = QPushButton(text)
            button.clicked.connect(lambda _checked=False, t=text: self._send(t))
            self._suggestions.append(button)
            suggestion_row.addWidget(button)
        suggestion_row.addStretch(1)

        self._status = QLabel()
        self._status.setObjectName("caption")
        self._input = QLineEdit()
        self._input.setPlaceholderText("Ask about your training…")
        self._input.returnPressed.connect(self._on_send_clicked)
        self._send_button = QPushButton("Send")
        self._send_button.setObjectName("primary")
        self._send_button.clicked.connect(self._on_send_clicked)
        input_row = QHBoxLayout()
        input_row.addWidget(self._input, 1)
        input_row.addWidget(self._send_button)

        layout = QVBoxLayout(self)
        layout.addLayout(header)
        layout.addWidget(self._transcript, 1)
        layout.addLayout(suggestion_row)
        layout.addWidget(self._status)
        layout.addLayout(input_row)
        self._render()

    # -- user actions ----------------------------------------------------------------

    def _on_send_clicked(self) -> None:
        self._send(self._input.text())

    def _on_new_chat(self) -> None:
        if self._busy:
            return
        self._agent.reset()
        self._entries.clear()
        self._status.setText("")
        self._render()

    def _send(self, text: str) -> None:
        question = text.strip()
        if self._busy or not question:
            return
        self._last_question = question
        self._entries.append(("user", question))
        self._input.clear()
        self._set_busy(True)
        self._status.setText("Thinking… a local model can take a while.")
        self._render()
        threading.Thread(target=self._work, args=(question,), daemon=True).start()

    # -- background work -------------------------------------------------------------

    def _work(self, question: str) -> None:
        try:
            answer = self._agent.ask(question, on_tool=self._bridge.progress.emit)
        except PoseTrackerError as exc:
            logger.warning("Chat request failed: %s", exc)
            self._bridge.failed.emit(str(exc))
        except Exception:  # thread boundary: show it instead of dying silently
            logger.exception("Chat request failed")
            self._bridge.failed.emit(
                "Something went wrong while asking the assistant. See the log for details."
            )
        else:
            self._bridge.answered.emit(answer)

    def _on_progress(self, tool_name: str) -> None:
        self._status.setText(f"Looking at your data ({tool_name})…")

    def _on_answered(self, answer: ChatAnswer) -> None:
        text = answer.text
        if answer.tools_used:
            text += f"\n\n*Data used: {', '.join(answer.tools_used)}*"
        self._entries.append(("assistant", text))
        self._finish()

    def _on_failed(self, message: str) -> None:
        self._entries.append(("error", message))
        self._input.setText(self._last_question)  # so it can be sent again
        self._finish()

    def _finish(self) -> None:
        self._status.setText("")
        self._set_busy(False)
        self._render()
        self._input.setFocus()

    # -- rendering -------------------------------------------------------------------

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        for widget in (self._input, self._send_button, self._new, *self._suggestions):
            widget.setEnabled(not busy)

    def _render(self) -> None:
        for button in self._suggestions:
            button.setVisible(not self._entries)
        if not self._entries:
            self._transcript.setHtml(_EMPTY_HTML)
            return
        parts: list[str] = []
        for kind, text in self._entries:
            if kind == "user":
                quoted = "\n".join(f"> {line}" for line in text.splitlines() or [""])
                parts.append(f"**You**\n\n{quoted}")
            elif kind == "assistant":
                parts.append(f"**Coach**\n\n{text}")
            else:
                parts.append(f"**Problem**\n\n{text}")
        self._transcript.setMarkdown("\n\n---\n\n".join(parts))
        bar = self._transcript.verticalScrollBar()
        bar.setValue(bar.maximum())