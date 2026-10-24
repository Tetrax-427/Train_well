from __future__ import annotations

from pathlib import Path

import pytest

from pose_tracker.application.chat.llm_settings import parse_llm_settings
from pose_tracker.config import LlmSettings
from pose_tracker.errors import LlmConfigError
from pose_tracker.infrastructure.llm_settings_file import read_llm_settings_file


def problems(data: dict[str, object]) -> str:
    with pytest.raises(LlmConfigError) as info:
        parse_llm_settings(data, Path("llm.toml"))
    return str(info.value)


def test_no_data_means_the_defaults() -> None:
    assert parse_llm_settings({}) == LlmSettings()


def test_values_are_applied_and_numbers_are_converted() -> None:
    settings = parse_llm_settings({
        "base_url": "http://192.168.1.50:8080/v1", "model": "qwen", "timeout_s": 60,
        "max_tool_steps": 4, "api_key": "k",
    })
    assert (settings.base_url, settings.model, settings.api_key) == (
        "http://192.168.1.50:8080/v1", "qwen", "k"
    )
    assert settings.timeout_s == 60.0 and isinstance(settings.timeout_s, float)
    assert settings.max_tool_steps == 4


def test_typos_get_a_suggestion_and_every_problem_is_listed() -> None:
    text = problems({"modle": "x", "timeout_s": "slow", "max_tool_steps": 2.5})
    assert text.startswith("llm.toml has 3 problems:")
    assert "Did you mean 'model'" in text
    assert "timeout_s: expected a number" in text
    assert "max_tool_steps: expected a whole number" in text


def test_wrong_types_are_rejected() -> None:
    assert "expected text" in problems({"model": 5})
    assert "not true/false" in problems({"api_key": True})


@pytest.mark.parametrize("data", [
    {"base_url": "192.168.1.50:8080"},
    {"model": "  "},
    {"timeout_s": 0},
    {"temperature": 3},
    {"max_tool_steps": 0},
    {"max_history_turns": 99},
])
def test_invalid_values_are_rejected(data: dict[str, object]) -> None:
    assert "1 problem" in problems(data)


def test_the_file_reader(tmp_path: Path) -> None:
    path = tmp_path / "llm.toml"
    assert read_llm_settings_file(path) == {}  # a missing file means the defaults
    path.write_text('model = "qwen"\ntimeout_s = 60\n')
    assert read_llm_settings_file(path) == {"model": "qwen", "timeout_s": 60}
    path.write_text("model = ")
    with pytest.raises(LlmConfigError, match="not valid TOML"):
        read_llm_settings_file(path)
    with pytest.raises(LlmConfigError, match="Cannot read"):
        read_llm_settings_file(tmp_path)  # a directory

def test_the_context_size_can_be_set() -> None:
    assert parse_llm_settings({"context_tokens": 8192}).context_tokens == 8192