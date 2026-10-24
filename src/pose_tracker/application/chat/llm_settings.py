from __future__ import annotations

import dataclasses
import difflib
import math
from collections.abc import Collection, Mapping
from pathlib import Path
from typing import Any

from pose_tracker.config import LlmSettings
from pose_tracker.errors import LlmConfigError


def parse_llm_settings(data: Mapping[str, Any], source: Path | None = None) -> LlmSettings:
    """Apply the contents of llm.toml on top of the defaults. Every problem is reported at
    once. Raises LlmConfigError."""
    defaults = LlmSettings()
    known = {f.name: getattr(defaults, f.name) for f in dataclasses.fields(defaults)}
    problems: list[str] = []
    values: dict[str, Any] = {}
    for name, value in data.items():
        if name not in known:
            problems.append(f"{name}: unknown setting.{_suggest(name, known)}")
            continue
        stored, error = _convert(known[name], value)
        if error is None:
            values[name] = stored
        else:
            problems.append(f"{name}: {error}")
    if not problems:
        try:
            return dataclasses.replace(defaults, **values)
        except ValueError as exc:
            problems.append(str(exc))
    label = source.name if source is not None else "The LLM settings"
    count = len(problems)
    lines = [f"{label} has {count} problem{'s' if count != 1 else ''}:"]
    lines += [f"  - {problem}" for problem in problems]
    raise LlmConfigError("\n".join(lines))


def _convert(current: Any, value: Any) -> tuple[Any, str | None]:
    if isinstance(value, bool):
        return None, "expected text or a number, not true/false"
    if isinstance(current, str):
        if isinstance(value, str):
            return value, None
        return None, 'expected text in quotes, for example "http://192.168.1.50:8080/v1"'
    if isinstance(current, int):
        return (value, None) if isinstance(value, int) else (None, "expected a whole number")
    if isinstance(current, float):
        if isinstance(value, (int, float)) and math.isfinite(value):
            return float(value), None
        return None, "expected a number"
    return None, "this setting cannot be changed"


def _suggest(name: str, options: Collection[str]) -> str:
    close = difflib.get_close_matches(name, list(options), n=1)
    if close:
        return f" Did you mean '{close[0]}'?"
    return f" Valid: {', '.join(sorted(options))}."