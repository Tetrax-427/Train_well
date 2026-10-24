from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass

from pose_tracker.domain.chat import ToolSpec

CHARS_PER_TOKEN = 3          # deliberately pessimistic: numbers and JSON tokenize badly
MESSAGE_OVERHEAD = 8         # tokens a chat template adds around every message
MIN_CONTEXT_FOR_TOOLS = 4096
RESERVE_TOKENS = 400         # room for the question, a little history and slack
DEFAULT_REPLY_TOKENS = 512
MIN_DIGEST_CHARS = 600
MAX_DIGEST_CHARS = 4000
MIN_TOOL_RESULT_CHARS = 1000
MAX_TOOL_RESULT_CHARS = 8000


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def tools_tokens(specs: Sequence[ToolSpec]) -> int:
    """What offering these tools costs in the prompt."""
    if not specs:
        return 0
    payload = [
        {"name": s.name, "description": s.description, "parameters": dict(s.parameters)}
        for s in specs
    ]
    return estimate_tokens(json.dumps(payload))


@dataclass(frozen=True, slots=True)
class ChatBudget:
    """How the model's context is spent."""

    context_tokens: int
    reply_tokens: int          # held back for the answer
    tools_enabled: bool
    digest_chars: int          # size of the training summary
    tool_result_chars: int     # longest tool result passed back to the model

    @property
    def prompt_tokens(self) -> int:
        return self.context_tokens - self.reply_tokens


def plan_budget(
    context_tokens: int, max_tokens: int, base_prompt_tokens: int, tool_tokens: int
) -> ChatBudget:
    """Split a context window between the prompt, the tool descriptions and the reply.

    Tools are offered only when the context is big enough to hold their descriptions next
    to a useful summary. Otherwise the summary gets the room instead.
    """
    if context_tokens <= 0:
        raise ValueError("context_tokens must be positive")
    reply = min(max_tokens if max_tokens > 0 else DEFAULT_REPLY_TOKENS, context_tokens // 4)
    prompt = context_tokens - reply
    fixed = base_prompt_tokens + RESERVE_TOKENS
    smallest_digest = MIN_DIGEST_CHARS // CHARS_PER_TOKEN
    tools_enabled = (
        context_tokens >= MIN_CONTEXT_FOR_TOOLS and fixed + tool_tokens + smallest_digest <= prompt
    )
    spare = prompt - fixed - (tool_tokens if tools_enabled else 0)
    digest_chars = min(max(spare * CHARS_PER_TOKEN, MIN_DIGEST_CHARS), MAX_DIGEST_CHARS)
    tool_result_chars = min(
        max(prompt * CHARS_PER_TOKEN // 4, MIN_TOOL_RESULT_CHARS), MAX_TOOL_RESULT_CHARS
    )
    return ChatBudget(context_tokens, reply, tools_enabled, digest_chars, tool_result_chars)