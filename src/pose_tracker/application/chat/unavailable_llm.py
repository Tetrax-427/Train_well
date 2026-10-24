from __future__ import annotations

from collections.abc import Sequence

from pose_tracker.domain.chat import ChatMessage, LlmReply, ToolSpec
from pose_tracker.errors import LlmError


class UnavailableLlmClient:
    """Stands in for a backend that could not be configured; every call explains why."""

    def __init__(self, reason: str) -> None:
        self._reason = reason

    def complete(self, messages: Sequence[ChatMessage], tools: Sequence[ToolSpec]) -> LlmReply:
        raise LlmError(self._reason)