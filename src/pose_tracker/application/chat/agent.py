from __future__ import annotations

import json
from collections.abc import Callable

from pose_tracker.application.chat.budget import (
    CHARS_PER_TOKEN,
    DEFAULT_REPLY_TOKENS,
    MESSAGE_OVERHEAD,
    estimate_tokens,
    tools_tokens,
)
from pose_tracker.application.chat.conversation import Conversation
from pose_tracker.application.chat.tool_registry import ToolRegistry, error_json
from pose_tracker.domain.chat import ChatAnswer, ChatMessage, ToolCall
from pose_tracker.errors import ChatError
from pose_tracker.interfaces import LlmClient

_CUT = " ...[output cut off: ask again with filters such as exercise or days]"
_MIN_RESULT_CHARS = 300


def _tokens(message: ChatMessage) -> int:
    tokens = estimate_tokens(message.content) + MESSAGE_OVERHEAD
    for call in message.tool_calls:
        tokens += estimate_tokens(call.name + json.dumps(dict(call.arguments), default=str))
    return tokens


class ChatAgent:
    """Answers a question by letting the model call tools until it can reply.

    With ``context_tokens`` the agent keeps every request inside the model's context:
    older turns are dropped and tool results are cut to the room left. Without it nothing
    is measured.

    Not thread-safe: ask one question at a time. History only changes when an answer was
    produced, so a failed question can simply be asked again.
    """

    def __init__(
        self,
        llm: LlmClient,
        tools: ToolRegistry,
        system_prompt: Callable[[], str],
        max_tool_steps: int = 6,
        max_tool_chars: int = 8000,
        max_history_turns: int = 8,
        context_tokens: int | None = None,
        reply_tokens: int = DEFAULT_REPLY_TOKENS,
    ) -> None:
        self._llm = llm
        self._tools = tools
        self._system_prompt = system_prompt
        self._max_tool_steps = max_tool_steps
        self._max_tool_chars = max_tool_chars
        self._history = Conversation(max_history_turns)
        self._prompt_budget = (
            None if context_tokens is None else max(context_tokens - reply_tokens, 0)
        )

    def reset(self) -> None:
        self._history.clear()

    def ask(self, text: str, on_tool: Callable[[str], None] | None = None) -> ChatAnswer:
        """Raises ValueError for an empty question, LlmError if the provider fails and
        ChatError if the model never produces an answer or the question cannot fit."""
        question = text.strip()
        if not question:
            raise ValueError("Type a question first.")
        system = ChatMessage.system(self._system_prompt())
        user = ChatMessage.user(question)
        fixed = _tokens(system) + tools_tokens(self._tools.specs)
        budget = self._prompt_budget

        history_room: int | None = None
        if budget is not None:
            if fixed + _tokens(user) > budget:
                raise ChatError(
                    "That question is too long for the model's context size. Shorten it, or "
                    "raise the server's context size and set context_tokens in llm.toml."
                )
            history_room = budget - fixed - _tokens(user)
        working = [*self._history.messages(history_room), user]
        used: list[str] = []

        for step in range(self._max_tool_steps + 1):
            offered = self._tools.specs if step < self._max_tool_steps else ()
            reply = self._llm.complete([system, *working], offered)
            if not reply.tool_calls:
                answer = reply.content.strip()
                if not answer:
                    raise ChatError("The assistant returned an empty answer. Try asking again.")
                self._history.add_turn(question, answer)
                return ChatAnswer(answer, tuple(dict.fromkeys(used)))
            if step == self._max_tool_steps:
                break  # no tools were offered, yet it still asked for one
            working.append(ChatMessage.assistant(reply.content, reply.tool_calls))
            for call in reply.tool_calls:
                if self._tools.has(call.name):
                    used.append(call.name)
                if on_tool is not None:
                    on_tool(call.name)
                room: int | None = None
                if budget is not None:
                    spent = fixed + sum(_tokens(m) for m in working)
                    room = max(budget - spent, 0) * CHARS_PER_TOKEN
                working.append(ChatMessage.tool(call.call_id, self._run(call, room)))
        raise ChatError(
            "The assistant kept asking for data without giving an answer. "
            "Try a more specific question."
        )

    def _run(self, call: ToolCall, room_chars: int | None) -> str:
        if call.argument_error is not None:
            text = error_json(
                f"Could not read the arguments for '{call.name}': {call.argument_error}"
            )
        else:
            text = self._tools.run(call.name, call.arguments)
        limit = self._max_tool_chars
        if room_chars is not None:
            limit = min(limit, max(room_chars, _MIN_RESULT_CHARS))
        if len(text) > limit:
            text = text[:limit] + _CUT
        return text