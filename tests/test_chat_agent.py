from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest

from pose_tracker.application.chat.agent import ChatAgent
from pose_tracker.application.chat.conversation import Conversation
from pose_tracker.application.chat.system_prompt import build_system_prompt
from pose_tracker.application.chat.tool_registry import ToolRegistry
from pose_tracker.domain.chat import ChatMessage, LlmReply, Role, ToolCall, ToolSpec
from pose_tracker.errors import ChatError, LlmError


class ScriptedLlm:
    def __init__(self, *replies: LlmReply | Exception) -> None:
        self.replies = list(replies)
        self.calls: list[tuple[list[ChatMessage], tuple[ToolSpec, ...]]] = []

    def complete(self, messages: Sequence[ChatMessage], tools: Sequence[ToolSpec]) -> LlmReply:
        self.calls.append((list(messages), tuple(tools)))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


class Lookup:
    def __init__(self, payload: Any = None) -> None:
        self.spec = ToolSpec("lookup", "d", {"type": "object", "properties": {}})
        self.runs = 0
        self._payload = {"value": 42} if payload is None else payload

    def run(self, arguments: Any) -> Any:
        self.runs += 1
        return self._payload


def agent_for(llm: ScriptedLlm, tool: Lookup | None = None, **kwargs: Any) -> ChatAgent:
    return ChatAgent(llm, ToolRegistry([tool or Lookup()]), lambda: "SYSTEM", **kwargs)


def call(name: str = "lookup", call_id: str = "c1", **kwargs: Any) -> LlmReply:
    return LlmReply("", (ToolCall(call_id, name, {}, **kwargs),))


def roles(messages: list[ChatMessage]) -> list[Role]:
    return [m.role for m in messages]


def test_a_direct_answer_needs_no_tools() -> None:
    llm = ScriptedLlm(LlmReply("You trained twice."))
    tool = Lookup()
    answer = agent_for(llm, tool).ask("  How was my week? ")
    assert (answer.text, answer.tools_used) == ("You trained twice.", ())
    messages, offered = llm.calls[0]
    assert messages == [ChatMessage.system("SYSTEM"), ChatMessage.user("How was my week?")]
    assert offered == (tool.spec,) and tool.runs == 0


def test_tool_results_are_fed_back_until_the_model_answers() -> None:
    llm = ScriptedLlm(call(), LlmReply("It is 42."))
    tool, seen = Lookup(), []
    answer = agent_for(llm, tool).ask("What is it?", on_tool=seen.append)

    assert (answer.text, answer.tools_used, seen, tool.runs) == ("It is 42.", ("lookup",), ["lookup"], 1)
    messages, _ = llm.calls[1]
    assert roles(messages) == [Role.SYSTEM, Role.USER, Role.ASSISTANT, Role.TOOL]
    assert messages[2].tool_calls[0].name == "lookup"
    assert (messages[3].content, messages[3].tool_call_id) == ('{"value": 42}', "c1")


def test_only_the_questions_and_answers_are_kept_between_turns() -> None:
    llm = ScriptedLlm(call(), LlmReply("a1"), LlmReply("a2"))
    agent = agent_for(llm)
    agent.ask("q1")
    agent.ask("q2")
    messages, _ = llm.calls[2]
    assert roles(messages) == [Role.SYSTEM, Role.USER, Role.ASSISTANT, Role.USER]
    assert [m.content for m in messages[1:]] == ["q1", "a1", "q2"]


def test_old_turns_are_dropped_beyond_the_history_limit() -> None:
    llm = ScriptedLlm(*(LlmReply(f"a{i}") for i in range(1, 5)))
    agent = agent_for(llm, max_history_turns=2)
    for question in ("q1", "q2", "q3", "q4"):
        agent.ask(question)
    users = [m.content for m in llm.calls[3][0] if m.role is Role.USER]
    assert users == ["q2", "q3", "q4"]


def test_a_failed_question_leaves_no_trace_and_can_be_asked_again() -> None:
    llm = ScriptedLlm(LlmError("server down"), LlmReply("ok"))
    agent = agent_for(llm)
    with pytest.raises(LlmError):
        agent.ask("q1")
    assert agent.ask("q2").text == "ok"
    assert [m.content for m in llm.calls[1][0][1:]] == ["q2"]


def test_unknown_tools_are_answered_with_an_error_and_not_counted() -> None:
    llm = ScriptedLlm(call(name="made_up"), LlmReply("sorry"))
    answer = agent_for(llm).ask("q")
    assert answer.tools_used == ()
    assert "Unknown tool 'made_up'" in llm.calls[1][0][-1].content


def test_arguments_the_model_got_wrong_are_reported_without_running_the_tool() -> None:
    llm = ScriptedLlm(call(argument_error="the arguments were not valid JSON"), LlmReply("ok"))
    tool = Lookup()
    agent_for(llm, tool).ask("q")
    assert tool.runs == 0
    assert "not valid JSON" in llm.calls[1][0][-1].content


def test_huge_tool_output_is_cut_off() -> None:
    llm = ScriptedLlm(call(), LlmReply("ok"))
    agent_for(llm, Lookup({"rows": "x" * 500}), max_tool_chars=100).ask("q")
    content = llm.calls[1][0][-1].content
    assert len(content) < 250 and "cut off" in content


def test_a_model_that_never_answers_is_stopped() -> None:
    llm = ScriptedLlm(call(call_id="a"), call(call_id="b"), call(call_id="c"))
    with pytest.raises(ChatError, match="without giving an answer"):
        agent_for(llm, max_tool_steps=2).ask("q")
    assert llm.calls[0][1] != () and llm.calls[-1][1] == ()  # the last round offered no tools


def test_empty_answers_and_empty_questions_are_rejected() -> None:
    with pytest.raises(ChatError, match="empty"):
        agent_for(ScriptedLlm(LlmReply("   "))).ask("q")
    with pytest.raises(ValueError):
        agent_for(ScriptedLlm()).ask("   ")


def test_reset_forgets_the_conversation() -> None:
    llm = ScriptedLlm(LlmReply("a1"), LlmReply("a2"))
    agent = agent_for(llm)
    agent.ask("q1")
    agent.reset()
    agent.ask("q2")
    assert [m.content for m in llm.calls[1][0][1:]] == ["q2"]


def test_the_conversation_keeps_the_most_recent_turns() -> None:
    conversation = Conversation(max_turns=2)
    for n in (1, 2, 3):
        conversation.add_turn(f"q{n}", f"a{n}")
    assert len(conversation) == 2
    assert [m.content for m in conversation.messages()] == ["q2", "a2", "q3", "a3"]
    conversation.clear()
    assert conversation.messages() == []
    with pytest.raises(ValueError):
        Conversation(0)


def test_the_system_prompt_names_the_date_and_the_exercises() -> None:
    from datetime import date

    prompt = build_system_prompt(date(2026, 10, 21), {"squat": "Squat", "row": "Bent-Over Row"})
    assert "2026" in prompt and "Squat, Bent-Over Row" in prompt

def test_conversation_keeps_the_newest_turns_that_fit() -> None:
    conversation = Conversation(max_turns=5)
    for n in (1, 2, 3):
        conversation.add_turn(f"q{n}", "a" * 30)  # each turn costs 1 + 10 + 16 = 27 tokens
    assert [m.content for m in conversation.messages(max_tokens=60)][::2] == ["q2", "q3"]
    assert conversation.messages(max_tokens=10) == []


def test_history_that_does_not_fit_the_context_is_left_out() -> None:
    llm = ScriptedLlm(LlmReply("a" * 300), LlmReply("ok"))
    agent = agent_for(llm, context_tokens=200, reply_tokens=50)
    agent.ask("q1")
    agent.ask("q2")
    assert [m.content for m in llm.calls[1][0][1:]] == ["q2"]


def test_history_that_fits_the_context_is_kept() -> None:
    llm = ScriptedLlm(LlmReply("short"), LlmReply("ok"))
    agent = agent_for(llm, context_tokens=200, reply_tokens=50)
    agent.ask("q1")
    agent.ask("q2")
    assert [m.content for m in llm.calls[1][0][1:]] == ["q1", "short", "q2"]


def test_a_question_that_cannot_fit_is_rejected_before_the_model_is_called() -> None:
    llm = ScriptedLlm()
    with pytest.raises(ChatError, match="too long"):
        agent_for(llm, context_tokens=100, reply_tokens=20).ask("x" * 1000)
    assert llm.calls == []


def test_tool_results_are_cut_to_the_room_left_in_the_context() -> None:
    llm = ScriptedLlm(call(), LlmReply("ok"))
    agent_for(llm, Lookup({"rows": "x" * 5000}), context_tokens=500, reply_tokens=100).ask("q")
    content = llm.calls[1][0][-1].content
    assert len(content) < 1300 and "cut off" in content