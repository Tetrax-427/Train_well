from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any


class ToolArgumentError(ValueError):
    """The model called a tool with arguments that cannot be used. The message goes back to it."""


class Arguments:
    """Checked access to a tool call's arguments. Missing and null values both mean 'not given'."""

    def __init__(self, raw: Mapping[str, Any], allowed: Collection[str]) -> None:
        unknown = sorted(set(raw) - set(allowed))
        if unknown:
            allowed_text = ", ".join(sorted(allowed)) or "none"
            raise ToolArgumentError(
                f"Unknown argument(s): {', '.join(unknown)}. Allowed: {allowed_text}."
            )
        self._raw = raw

    def text(self, name: str) -> str | None:
        value = self._raw.get(name)
        if value is None or value == "":
            return None
        if not isinstance(value, str):
            raise ToolArgumentError(f"'{name}' must be text.")
        return value.strip() or None

    def integer(
        self, name: str, minimum: int, maximum: int, default: int | None = None
    ) -> int | None:
        value = self._raw.get(name)
        if value is None or value == "":
            return default
        if isinstance(value, bool):
            raise ToolArgumentError(f"'{name}' must be a whole number.")
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        if isinstance(value, str):
            try:
                value = int(value.strip())
            except ValueError:
                raise ToolArgumentError(f"'{name}' must be a whole number.") from None
        if not isinstance(value, int):
            raise ToolArgumentError(f"'{name}' must be a whole number.")
        if not minimum <= value <= maximum:
            raise ToolArgumentError(f"'{name}' must be between {minimum} and {maximum}.")
        return value

    def require_integer(self, name: str, minimum: int, maximum: int) -> int:
        value = self.integer(name, minimum, maximum)
        if value is None:
            raise ToolArgumentError(f"'{name}' is required.")
        return value

    def boolean(self, name: str, default: bool = False) -> bool:
        value = self._raw.get(name)
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        raise ToolArgumentError(f"'{name}' must be true or false.")

    def day(self, name: str) -> date | None:
        text = self.text(name)
        if text is None:
            return None
        try:
            return date.fromisoformat(text)
        except ValueError:
            raise ToolArgumentError(f"'{name}' must be a date like 2026-10-21.") from None


def resolve_exercise(value: str | None, names: Mapping[str, str]) -> str | None:
    """The exercise key for a key or a display name (any case). None if not given."""
    if value is None:
        return None
    wanted = value.strip().lower()
    for key, name in names.items():
        if wanted in (key.lower(), name.lower()) or wanted.replace(" ", "_") == key.lower():
            return key
    raise ToolArgumentError(f"Unknown exercise '{value}'. Valid keys: {', '.join(names)}.")

@dataclass(frozen=True, slots=True)
class TimeWindow:
    """A range of time. ``until`` is exclusive; None means unbounded on that side."""

    since: datetime | None = None
    until: datetime | None = None

    def contains(self, moment: datetime) -> bool:
        return (self.since is None or moment >= self.since) and (
            self.until is None or moment < self.until
        )


def time_window(args: Arguments, today: date) -> TimeWindow:
    """The window described by ``days`` (last N days, today included) or by
    ``start_date`` / ``end_date`` (both inclusive). No filters means everything."""
    days = args.integer("days", 1, 3650)
    start, end = args.day("start_date"), args.day("end_date")
    if days is not None and (start is not None or end is not None):
        raise ToolArgumentError("Use either 'days' or 'start_date'/'end_date', not both.")
    if days is not None:
        return TimeWindow(since=datetime.combine(today - timedelta(days=days - 1), time.min))
    if start is not None and end is not None and start > end:
        raise ToolArgumentError("'start_date' must not be after 'end_date'.")
    return TimeWindow(
        since=datetime.combine(start, time.min) if start is not None else None,
        until=datetime.combine(end + timedelta(days=1), time.min) if end is not None else None,
    )