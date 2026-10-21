from __future__ import annotations

import pytest

from pose_tracker.domain.routine import MAX_NAME_LENGTH, clean_exercises, clean_name


def test_names_are_trimmed_and_inner_spaces_collapsed() -> None:
    assert clean_name("  Push   day ") == "Push day"


@pytest.mark.parametrize("name", ["", "   ", "x" * (MAX_NAME_LENGTH + 1)])
def test_bad_names_are_rejected(name: str) -> None:
    with pytest.raises(ValueError):
        clean_name(name)


def test_the_longest_allowed_name_is_accepted() -> None:
    assert clean_name("x" * MAX_NAME_LENGTH) == "x" * MAX_NAME_LENGTH


def test_exercises_keep_their_order() -> None:
    assert clean_exercises(["squat", "bench"], {"squat", "bench", "row"}) == ("squat", "bench")


def test_bad_exercise_lists_are_rejected() -> None:
    known = {"squat", "bench"}
    with pytest.raises(ValueError, match="at least one"):
        clean_exercises([], known)
    with pytest.raises(ValueError, match="only once"):
        clean_exercises(["squat", "squat"], known)
    with pytest.raises(ValueError, match="Unknown exercise: curl"):
        clean_exercises(["squat", "curl"], known)