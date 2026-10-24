from __future__ import annotations

from collections import deque

from pose_tracker.application.chat.budget import MESSAGE_OVERHEAD, estimate_tokens
from pose_tracker.domain.chat import ChatMessage


class Conversation:
    """The last few question/answer pairs. Tool output is not kept: once an answer exists
    it carries what mattered, and the model can look things up again."""

    def __init__(self, max_turns: int = 8) -> None:
        if max_turns < 1:
            raise ValueError("max_turns must be at least 1")
        self._turns: deque[tuple[str, str]] = deque(maxlen=max_turns)

    def __len__(self) -> int:
        return len(self._turns)

    def add_turn(self, question: str, answer: str) -> None:
        self._turns.append((question, answer))

    def messages(self, max_tokens: int | None = None) -> list[ChatMessage]:
        """The kept turns, oldest first. With ``max_tokens``, only the newest turns that fit."""
        turns = list(self._turns)
        if max_tokens is not None:
            kept: list[tuple[str, str]] = []
            spent = 0
            for question, answer in reversed(turns):
                cost = estimate_tokens(question) + estimate_tokens(answer) + 2 * MESSAGE_OVERHEAD
                if spent + cost > max_tokens:
                    break
                kept.append((question, answer))
                spent += cost
            turns = list(reversed(kept))
        messages: list[ChatMessage] = []
        for question, answer in turns:
            messages.append(ChatMessage.user(question))
            messages.append(ChatMessage.assistant(answer))
        return messages

    def clear(self) -> None:
        self._turns.clear()