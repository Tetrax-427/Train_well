from __future__ import annotations

from datetime import date, datetime

import pytest
from test_chat_tools import (
    NAMES,
    FakeProgress,
    FakeRoutines,
    FakeSessions,
    clock,
    progress_set,
    stored,
)

import pose_tracker.application.chat.digest as digest_module
from pose_tracker.application.chat.digest import TrainingDigest
from pose_tracker.application.chat.system_prompt import build_system_prompt
from pose_tracker.domain.routine import Routine
from pose_tracker.errors import PersistenceError
from pose_tracker.domain.progress import ProgressEntry

def digest_for(
    sessions: object = None, progress: object = None, routines: object = None
) -> TrainingDigest:
    return TrainingDigest(
        NAMES,
        sessions if sessions is not None else FakeSessions(),
        progress if progress is not None else FakeProgress(),
        routines if routines is not None else FakeRoutines(),
        clock,
    )


def test_recent_sessions_are_listed_with_what_was_saved() -> None:
    sessions = FakeSessions(
        stored(1, "squat", datetime(2026, 10, 15, 9, 30), [[], []]),
        stored(2, "squat", datetime(2026, 10, 20, 9, 30), [[], []]),
        stored(3, "bench_press", datetime(2026, 10, 21, 8, 0), [[]]),
    )
    sessions.sessions[2] = stored(
        2, "squat", datetime(2026, 10, 20, 9, 30), [[], []],
        progress=__import__("pose_tracker.domain.progress", fromlist=["ProgressEntry"]).ProgressEntry(12, 40.0),
    )
    text = digest_for(sessions).text()
    assert text.startswith("TRAINING SUMMARY")
    assert "- 2026-10-21 Bench Press: 1 rep, 1 clean" in text
    assert "- 2026-10-20 Squat: 2 reps, 2 clean; saved 40 kg x 12" in text
    assert "- 2026-10-15 Squat: 2 reps, 2 clean" in text
    assert text.index("2026-10-21") < text.index("2026-10-15")  # newest first


def test_common_mistakes_are_summarized() -> None:
    sessions = FakeSessions(
        stored(1, "squat", datetime(2026, 10, 18, 9, 0),
               [[("squat_depth", 110.0, 105.0)], [("torso_lean", 60.0, 50.0)]]),
        stored(2, "squat", datetime(2026, 10, 20, 9, 0), [[], [("squat_depth", 120.0, 100.0)]]),
    )
    text = digest_for(sessions).text()
    assert "(4 reps, 1 clean):" in text
    assert (
        "- Squat: squat_depth (msg squat_depth) x2 in 2 session(s), "
        "average 115 vs limit 100, last 2026-10-20" in text
    )


def test_progress_shows_bests_and_the_latest_day() -> None:
    progress = FakeProgress(progress_set(1, 19, 10, 12, 40.0), progress_set(2, 19, 11, 10, 50.0))
    text = digest_for(progress=progress).text()
    assert (
        "- Squat: 1 day(s), 2 set(s), heaviest 50 kg, most reps in a set 12; "
        "latest 2026-10-19: 40 kg x 12, 50 kg x 10" in text
    )
    assert "Bench Press" not in text.split("Progress")[1]  # exercises without sets are left out


def test_routines_are_listed() -> None:
    routines = FakeRoutines(Routine(1, "Push", ("bench_press",)))
    assert "Saved routines: Push (Bench Press)" in digest_for(routines=routines).text()


def test_a_user_with_no_data_is_told_so_plainly() -> None:
    text = digest_for().text()
    assert "Sessions: none in the last 14 days." in text
    assert "no reps recorded in the last 30 days" in text
    assert "nothing saved to progress in the last 90 days" in text
    assert "Routines: none saved." in text


class BrokenSessions:
    def list_sessions(self, exercise_key: str | None = None) -> list:
        raise PersistenceError("locked")

    def get_session(self, session_id: int) -> None:
        raise PersistenceError("locked")

    def delete_session(self, session_id: int) -> None: ...


def test_an_unreadable_part_does_not_take_the_rest_down() -> None:
    routines = FakeRoutines(Routine(1, "Push", ("bench_press",)))
    text = digest_for(sessions=BrokenSessions(), routines=routines).text()
    assert text.count("could not be read") == 2  # recent sessions and mistakes
    assert "Saved routines: Push (Bench Press)" in text


def test_an_oversized_summary_is_cut_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(digest_module, "MAX_CHARS", 60)
    assert digest_for().text().endswith("use the tools for the rest]")


def test_the_prompt_includes_the_summary_and_tells_the_model_not_to_ask() -> None:
    prompt = build_system_prompt(date(2026, 10, 21), NAMES, "TRAINING SUMMARY ...")
    assert "TRAINING SUMMARY ..." in prompt
    assert "Never ask the user to type in their training data" in prompt
    assert "TRAINING SUMMARY" not in build_system_prompt(date(2026, 10, 21), NAMES)

def test_recent_sessions_are_listed_with_what_was_saved() -> None:
    sessions = FakeSessions(
        stored(1, "squat", datetime(2026, 10, 15, 9, 30), [[], []]),
        stored(2, "squat", datetime(2026, 10, 20, 9, 30), [[], []], progress=ProgressEntry(12, 40.0)),
        stored(3, "bench_press", datetime(2026, 10, 21, 8, 0), [[]]),
    )
    text = digest_for(sessions).text()
    assert text.startswith("TRAINING SUMMARY")
    assert "- 2026-10-21 Bench Press: 1 rep, 1 clean" in text
    assert "- 2026-10-20 Squat: 2 reps, 2 clean; saved 40 kg x 12" in text
    assert "- 2026-10-15 Squat: 2 reps, 2 clean" in text
    assert text.index("2026-10-21") < text.index("2026-10-15")  # newest first


def test_a_small_budget_shortens_long_lists_but_keeps_every_section() -> None:
    sessions = FakeSessions(*(
        stored(i, "squat", datetime(2026, 10, 20, 9, i), [[("squat_depth", 110.0, 100.0)]])
        for i in range(1, 13)
    ))
    text = digest_for(sessions).text(max_chars=900)
    assert len(text) <= 900
    assert text.count("- 2026-10-20 Squat:") < 12   # the recent list was shortened
    assert "Most common form mistakes" in text       # but the mistakes were not squeezed out
    assert "nothing saved to progress" in text and "Routines: none saved." in text


def test_a_tiny_budget_still_gives_a_valid_summary() -> None:
    assert digest_for().text(max_chars=10).startswith("TRAINING SUMMARY")


def test_the_prompt_has_no_tool_advice_when_tools_are_off() -> None:
    with_tools = build_system_prompt(date(2026, 10, 21), NAMES, "TRAINING SUMMARY ...")
    without = build_system_prompt(date(2026, 10, 21), NAMES, "TRAINING SUMMARY ...", tools=False)
    assert "Use the tools only" in with_tools and "Use the tools only" not in without
    assert "say what is missing" in without