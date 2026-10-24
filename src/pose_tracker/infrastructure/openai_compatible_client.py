from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any
import logging
import time 
from pose_tracker.config import LlmSettings
from pose_tracker.domain.chat import ChatMessage, LlmReply, Role, ToolCall, ToolSpec
from pose_tracker.errors import LlmError
from pose_tracker.infrastructure.http_json import post_json

HttpPost = Callable[[str, Mapping[str, Any], Mapping[str, str], float], dict[str, Any]]

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)

logger = logging.getLogger(__name__)

class OpenAiCompatibleClient:
    """An LlmClient for any server that speaks the OpenAI chat-completions API with tool
    calling (llama.cpp, Ollama, vLLM, LM Studio and others)."""

    def __init__(self, settings: LlmSettings, post: HttpPost = post_json) -> None:
        self._settings = settings
        self._post = post
        self._url = settings.base_url.rstrip("/") + "/chat/completions"
        self._headers = {"Authorization": f"Bearer {settings.api_key}"} if settings.api_key else {}

    def complete(self, messages: Sequence[ChatMessage], tools: Sequence[ToolSpec]) -> LlmReply:
        settings = self._settings
        payload: dict[str, Any] = {
            "model": settings.model,
            "messages": [_message_json(m) for m in messages],
            "temperature": settings.temperature,
            "stream": False,
        }
        if settings.max_tokens > 0:
            payload["max_tokens"] = settings.max_tokens
        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": dict(t.parameters),
                    },
                }
                for t in tools
            ]
        logger.info(
            "LLM request: %s model=%s messages=%d tools=%d",
            self._url, settings.model, len(messages), len(tools),
        )
        started = time.perf_counter()
        try:
            reply = _parse_reply(self._post(self._url, payload, self._headers, settings.timeout_s))
        except LlmError as exc:
            logger.error("LLM request failed after %.1fs: %s", time.perf_counter() - started, exc)
            raise
        logger.info(
            "LLM reply after %.1fs: %d characters, %d tool call(s)",
            time.perf_counter() - started, len(reply.content), len(reply.tool_calls),
        )
        return reply


def _message_json(message: ChatMessage) -> dict[str, Any]:
    if message.role is Role.TOOL:
        return {"role": "tool", "tool_call_id": message.tool_call_id, "content": message.content}
    data: dict[str, Any] = {"role": message.role.value, "content": message.content}
    if message.tool_calls:
        data["tool_calls"] = [
            {
                "id": call.call_id,
                "type": "function",
                "function": {"name": call.name, "arguments": json.dumps(dict(call.arguments))},
            }
            for call in message.tool_calls
        ]
    return data


def _parse_reply(data: Mapping[str, Any]) -> LlmReply:
    try:
        message = data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        raise LlmError("The model server sent a reply in an unexpected format.") from None
    if not isinstance(message, Mapping):
        raise LlmError("The model server sent a reply in an unexpected format.")
    content = strip_reasoning(message.get("content") or "")
    calls = tuple(_parse_call(i, raw) for i, raw in enumerate(message.get("tool_calls") or ()))
    if not content and not calls:
        raise LlmError("The model returned an empty reply.")
    return LlmReply(content, calls)


def _parse_call(index: int, raw: Any) -> ToolCall:
    function = raw.get("function") if isinstance(raw, Mapping) else None
    name = function.get("name") if isinstance(function, Mapping) else None
    if not isinstance(name, str) or not name:
        raise LlmError("The model asked for a tool without naming it.")
    call_id = str(raw.get("id") or f"call_{index}")
    arguments = function.get("arguments", {})
    if isinstance(arguments, str):
        if not arguments.strip():
            arguments = {}
        else:
            try:
                arguments = json.loads(arguments)
            except ValueError:
                return ToolCall(call_id, name, {}, "the arguments were not valid JSON")
    if not isinstance(arguments, Mapping):
        return ToolCall(call_id, name, {}, "the arguments must be a JSON object")
    return ToolCall(call_id, name, arguments)


def strip_reasoning(text: str) -> str:
    """Drop the <think>...</think> reasoning some local models put in their replies."""
    text = _THINK_BLOCK.sub("", text)
    if "</think>" in text:  # the opening tag was part of the prompt
        text = text.rsplit("</think>", 1)[1]
    return text.strip()