from __future__ import annotations

from typing import Any

import pytest

from pose_tracker.config import LlmSettings
from pose_tracker.domain.chat import ChatMessage, ToolCall, ToolSpec
from pose_tracker.errors import LlmError
from pose_tracker.infrastructure.openai_compatible_client import (
    OpenAiCompatibleClient,
    strip_reasoning,
)

SPEC = ToolSpec("list_sessions", "List sessions.", {"type": "object", "properties": {}})
SETTINGS = LlmSettings(
    base_url="http://server:8080/v1/", model="m", api_key="secret",
    timeout_s=30.0, temperature=0.2, max_tokens=256,
)


class FakePost:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.requests: list[tuple[str, dict[str, Any], dict[str, str], float]] = []

    def __call__(self, url: str, payload: Any, headers: Any, timeout: float) -> dict[str, Any]:
        self.requests.append((url, dict(payload), dict(headers), timeout))
        return self.response


def reply(message: dict[str, Any]) -> dict[str, Any]:
    return {"choices": [{"message": message}]}


def complete(response: dict[str, Any], settings: LlmSettings = SETTINGS):
    return OpenAiCompatibleClient(settings, FakePost(response)).complete(
        [ChatMessage.user("hi")], [SPEC]
    )


def test_the_request_has_the_expected_shape() -> None:
    post = FakePost(reply({"content": "hi"}))
    OpenAiCompatibleClient(SETTINGS, post).complete(
        [ChatMessage.system("sys"), ChatMessage.user("q")], [SPEC]
    )
    url, payload, headers, timeout = post.requests[0]
    assert url == "http://server:8080/v1/chat/completions"
    assert headers == {"Authorization": "Bearer secret"} and timeout == 30.0
    assert (payload["model"], payload["temperature"], payload["max_tokens"]) == ("m", 0.2, 256)
    assert payload["stream"] is False
    assert payload["messages"] == [
        {"role": "system", "content": "sys"}, {"role": "user", "content": "q"}
    ]
    assert payload["tools"] == [{
        "type": "function",
        "function": {"name": "list_sessions", "description": "List sessions.",
                     "parameters": {"type": "object", "properties": {}}},
    }]


def test_optional_parts_are_left_out() -> None:
    post = FakePost(reply({"content": "hi"}))
    settings = LlmSettings(max_tokens=0)
    OpenAiCompatibleClient(settings, post).complete([ChatMessage.user("q")], [])
    _, payload, headers, _ = post.requests[0]
    assert "tools" not in payload and "max_tokens" not in payload and headers == {}


def test_tool_calls_and_results_are_sent_in_the_openai_format() -> None:
    post = FakePost(reply({"content": "ok"}))
    messages = [
        ChatMessage.user("q"),
        ChatMessage.assistant("", (ToolCall("c1", "list_sessions", {"days": 7}),)),
        ChatMessage.tool("c1", '{"ok": 1}'),
    ]
    OpenAiCompatibleClient(SETTINGS, post).complete(messages, [SPEC])
    assert post.requests[0][1]["messages"][1:] == [
        {"role": "assistant", "content": "", "tool_calls": [{
            "id": "c1", "type": "function",
            "function": {"name": "list_sessions", "arguments": '{"days": 7}'},
        }]},
        {"role": "tool", "tool_call_id": "c1", "content": '{"ok": 1}'},
    ]


def test_a_plain_answer_is_parsed() -> None:
    result = complete(reply({"content": "  Hello  "}))
    assert (result.content, result.tool_calls) == ("Hello", ())


def test_tool_calls_are_parsed_whether_the_arguments_are_text_or_an_object() -> None:
    result = complete(reply({"content": None, "tool_calls": [
        {"id": "a", "type": "function", "function": {"name": "t", "arguments": '{"days": 7}'}},
        {"id": "b", "type": "function", "function": {"name": "t", "arguments": {"days": 2}}},
        {"function": {"name": "t", "arguments": ""}},
    ]}))
    first, second, third = result.tool_calls
    assert (first.call_id, dict(first.arguments)) == ("a", {"days": 7})
    assert (second.call_id, dict(second.arguments)) == ("b", {"days": 2})
    assert (third.call_id, dict(third.arguments)) == ("call_2", {})  # a missing id is made up


@pytest.mark.parametrize("arguments", ["{not json", "[1, 2]", 5])
def test_unusable_arguments_are_flagged_not_fatal(arguments: Any) -> None:
    result = complete(reply({"tool_calls": [
        {"id": "a", "function": {"name": "t", "arguments": arguments}}
    ]}))
    assert result.tool_calls[0].argument_error is not None


def test_reasoning_blocks_are_removed() -> None:
    assert strip_reasoning("<think>hmm\nmore</think>\n\nAnswer") == "Answer"
    assert strip_reasoning("reasoning</think>Answer") == "Answer"
    assert complete(reply({"content": "<think>x</think>Hi"})).content == "Hi"


@pytest.mark.parametrize("response", [
    {}, {"choices": []}, {"choices": [{"message": "text"}]},
    reply({"content": "   "}),
    reply({"tool_calls": [{"function": {"arguments": "{}"}}]}),
])
def test_unusable_replies_raise_llm_error(response: dict[str, Any]) -> None:
    with pytest.raises(LlmError):
        complete(response)