from __future__ import annotations

import pytest

from pose_tracker.application.chat.budget import (
    MAX_DIGEST_CHARS,
    MIN_DIGEST_CHARS,
    estimate_tokens,
    plan_budget,
    tools_tokens,
)
from pose_tracker.domain.chat import ToolSpec


def test_token_estimates_round_up() -> None:
    assert (estimate_tokens(""), estimate_tokens("abc"), estimate_tokens("abcd")) == (0, 1, 2)


def test_tools_cost_nothing_when_there_are_none() -> None:
    assert tools_tokens([]) == 0
    assert tools_tokens([ToolSpec("t", "d", {"type": "object", "properties": {}})]) > 0


def test_a_small_context_drops_the_tools_and_shrinks_the_summary() -> None:
    budget = plan_budget(2048, 1024, base_prompt_tokens=500, tool_tokens=900)
    assert (budget.reply_tokens, budget.prompt_tokens) == (512, 1536)
    assert not budget.tools_enabled
    assert budget.digest_chars == 1908  # (1536 - 500 - 400) tokens x 3 characters


def test_a_roomy_context_keeps_tools_and_a_full_summary() -> None:
    budget = plan_budget(8192, 1024, 500, 900)
    assert budget.tools_enabled and budget.digest_chars == MAX_DIGEST_CHARS
    assert budget.tool_result_chars == 5376


def test_tools_need_a_big_enough_context_and_room_for_their_descriptions() -> None:
    assert plan_budget(4096, 1024, 500, 900).tools_enabled
    assert not plan_budget(4096, 1024, 500, 2500).tools_enabled
    assert not plan_budget(3000, 1024, 500, 100).tools_enabled


def test_the_summary_never_shrinks_below_a_useful_minimum() -> None:
    assert plan_budget(1024, 1024, 900, 0).digest_chars == MIN_DIGEST_CHARS


def test_a_reply_length_of_zero_uses_a_default_reserve() -> None:
    assert plan_budget(8192, 0, 500, 0).reply_tokens == 512


def test_a_context_size_must_be_positive() -> None:
    with pytest.raises(ValueError):
        plan_budget(0, 1024, 500, 0)