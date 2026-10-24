from __future__ import annotations

import json
from typing import Any

import pytest

from pose_tracker.application.chat.tool_arguments import ToolArgumentError
from pose_tracker.application.chat.tool_registry import ToolRegistry
from pose_tracker.domain.chat import ToolSpec
from pose_tracker.errors import PersistenceError


class Tool:
    def __init__(self, name: str, behaviour: Any = None) -> None:
        self.spec = ToolSpec(name, "d", {"type": "object", "properties": {}})
        self._behaviour = behaviour

    def run(self, arguments: Any) -> Any:
        if isinstance(self._behaviour, Exception):
            raise self._behaviour
        return {"got": dict(arguments)}


def test_results_are_returned_as_json_text() -> None:
    registry = ToolRegistry([Tool("echo")])
    assert json.loads(registry.run("echo", {"days": 7})) == {"got": {"days": 7}}
    assert registry.has("echo") and not registry.has("nope")
    assert [s.name for s in registry.specs] == ["echo"]


def test_unknown_tools_get_an_error_that_lists_the_real_ones() -> None:
    error = json.loads(ToolRegistry([Tool("a"), Tool("b")]).run("c", {}))["error"]
    assert "Unknown tool 'c'" in error and "a, b" in error


def test_bad_arguments_become_an_error_the_model_can_read() -> None:
    registry = ToolRegistry([Tool("t", ToolArgumentError("'days' must be a whole number."))])
    assert json.loads(registry.run("t", {})) == {"error": "'days' must be a whole number."}


def test_storage_and_unexpected_failures_never_raise() -> None:
    registry = ToolRegistry([
        Tool("db", PersistenceError("locked")), Tool("bug", RuntimeError("boom")),
    ])
    assert "could not be read" in json.loads(registry.run("db", {}))["error"]
    assert "failed unexpectedly" in json.loads(registry.run("bug", {}))["error"]


def test_duplicate_tool_names_are_rejected() -> None:
    with pytest.raises(ValueError, match="'a'"):
        ToolRegistry([Tool("a"), Tool("a")])