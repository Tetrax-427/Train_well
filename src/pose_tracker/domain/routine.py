from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass

MAX_NAME_LENGTH = 40


@dataclass(frozen=True, slots=True)
class Routine:
    """A named, ordered list of exercises, for example Push day."""

    routine_id: int
    name: str
    exercise_keys: tuple[str, ...]


def clean_name(name: str) -> str:
    """The name without stray whitespace. Raises ValueError if it is empty or too long."""
    cleaned = " ".join(name.split())
    if not cleaned:
        raise ValueError("Give the routine a name.")
    if len(cleaned) > MAX_NAME_LENGTH:
        raise ValueError(f"Keep the name to {MAX_NAME_LENGTH} characters or fewer.")
    return cleaned


def clean_exercises(keys: Sequence[str], known: Collection[str]) -> tuple[str, ...]:
    """The exercise keys as a tuple. Raises ValueError if the list is empty, repeats an
    exercise or names one that does not exist."""
    if not keys:
        raise ValueError("Add at least one exercise.")
    if len(set(keys)) != len(keys):
        raise ValueError("Each exercise can be in a routine only once.")
    unknown = [key for key in keys if key not in known]
    if unknown:
        raise ValueError(f"Unknown exercise: {unknown[0]}")
    return tuple(keys)