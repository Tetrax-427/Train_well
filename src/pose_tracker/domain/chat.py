from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any


class Role(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A request from the model to run one tool."""

    call_id: str
    name: str
    arguments: Mapping[str, Any]
    argument_error: str | None = None  # set when the model's arguments could not be understood


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: Role
    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None  # on TOOL messages: which call this answers

    @classmethod
    def system(cls, text: str) -> ChatMessage:
        return cls(Role.SYSTEM, text)

    @classmethod
    def user(cls, text: str) -> ChatMessage:
        return cls(Role.USER, text)

    @classmethod
    def assistant(cls, text: str, tool_calls: tuple[ToolCall, ...] = ()) -> ChatMessage:
        return cls(Role.ASSISTANT, text, tool_calls)

    @classmethod
    def tool(cls, call_id: str, content: str) -> ChatMessage:
        return cls(Role.TOOL, content, tool_call_id=call_id)


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """What the model is told about a tool. ``parameters`` is a JSON Schema object."""

    name: str
    description: str
    parameters: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class LlmReply:
    content: str
    tool_calls: tuple[ToolCall, ...] = ()


@dataclass(frozen=True, slots=True)
class ChatAnswer:
    text: str
    tools_used: tuple[str, ...] = ()