from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from typing import Any

from pose_tracker.application.chat.tool_arguments import ToolArgumentError
from pose_tracker.domain.chat import ToolSpec
from pose_tracker.errors import PersistenceError
from pose_tracker.interfaces import ChatTool

logger = logging.getLogger(__name__)


def error_json(message: str) -> str:
    return json.dumps({"error": message})


class ToolRegistry:
    """The tools the model may call. Running one never raises: problems become an error
    result the model can read and react to."""

    def __init__(self, tools: Sequence[ChatTool]) -> None:
        self._tools: dict[str, ChatTool] = {}
        for tool in tools:
            name = tool.spec.name
            if name in self._tools:
                raise ValueError(f"Two tools are named '{name}'")
            self._tools[name] = tool

    @property
    def specs(self) -> tuple[ToolSpec, ...]:
        return tuple(tool.spec for tool in self._tools.values())

    def has(self, name: str) -> bool:
        return name in self._tools

    def run(self, name: str, arguments: Mapping[str, Any]) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return error_json(f"Unknown tool '{name}'. Available: {', '.join(self._tools)}.")
        try:
            result = tool.run(arguments)
        except ToolArgumentError as exc:
            return error_json(str(exc))
        except PersistenceError:
            logger.exception("Tool %s could not read the training data", name)
            return error_json("The training data could not be read right now.")
        except Exception:  # boundary of model-driven calls: report it to the model, keep chatting
            logger.exception("Tool %s failed", name)
            return error_json(f"The tool '{name}' failed unexpectedly.")
        return json.dumps(result, ensure_ascii=False, default=str)