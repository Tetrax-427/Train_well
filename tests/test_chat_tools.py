from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import pytest

from pose_tracker.application.catalog_factory import catalog_for
from pose_tracker.application.chat.tool_arguments import ToolArgumentError
from pose_tracker.application.chat.tool_registry import ToolRegistry
from pose_tracker.application.chat.tools import (
    GetSessionTool,
    ListExercisesTool,
    ListRoutinesTool,
    ListSessionsTool,
    MistakeSummaryTool,
    ProgressHistoryTool,
    default_tools,
)
from pose_tracker.config import AppConfig
from pose_tracker.domain.history import (
    SessionSummary,
    StoredRep,
    StoredSession,
    StoredViolation,
)
from pose_tracker.domain.pose import Pose
from pose_tracker.domain.progress import ProgressEntry, ProgressSet
from pose_tracker.domain.routine import Routine

NOW = datetime(2026, 10, 21, 18, 0)
NAMES = {"squat": "Squat", "bench_press": "Bench Press"}


def clock() -> datetime:
    return NOW


def stored(
    session_id: int, key: str, started: datetime,
    reps: Sequence[Sequence[tuple[str, float, float]]] = (),
    ended: datetime | None = None, progress: ProgressEntry | None = None,
) -> StoredSession:
    """``reps`` holds one list of (rule, measured, limit) issues per rep."""
    rep_rows = tuple(
        StoredRep(
            number, started, 2000, {"knee_angle": (95.0, 170.0)},
            tuple(
                StoredViolation(rule, f"msg {rule}", f"why {rule}", measured, limit, 1000, Pose(()), None)
                for rule, measured, limit in issues
            ),
        )
        for number, issues in enumerate(reps, start=1)
    )
    clean = sum(1 for issues in reps if not issues)
    summary = SessionSummary(session_id, key, NAMES[key], started, ended, len(reps), clean, progress)
    return StoredSession(summary, rep_rows)


class FakeSessions:
    def __init__(self, *sessions: StoredSession) -> None:
        self.sessions = {s.summary.session_id: s for s in sessions}

    def list_sessions(self, exercise_key: str | None = None) -> list[SessionSummary]:
        rows = [
            s.summary for s in self.sessions.values()
            if exercise_key in (None, s.summary.exercise_key)
        ]
        return sorted(rows, key=lambda r: (r.started_at, r.session_id), reverse=True)

    def get_session(self, session_id: int) -> StoredSession | None:
        return self.sessions.get(session_id)

    def delete_session(self, session_id: int) -> None:
        self.sessions.pop(session_id, None)


class FakeProgress:
    def __init__(self, *sets: ProgressSet) -> None:
        self.sets = list(sets)

    def list_progress_sets(self, exercise_key: str, since: datetime | None = None) -> list[ProgressSet]:
        return sorted(
            (s for s in self.sets if s.exercise_key == exercise_key
             and (since is None or s.performed_at >= since)),
            key=lambda s: (s.performed_at, s.session_id),
        )

    def latest_progress_day(self, exercise_key: str) -> list[ProgressSet]:
        return []


class FakeRoutines:
    def __init__(self, *routines: Routine) -> None:
        self.routines = list(routines)

    def list_routines(self) -> list[Routine]:
        return self.routines


SESSIONS = FakeSessions(
    stored(1, "squat", datetime(2026, 10, 15, 9, 30), [[], []]),
    stored(2, "squat", datetime(2026, 10, 20, 9, 30), [[], []], progress=ProgressEntry(12, 40.0)),
    stored(3, "bench_press", datetime(2026, 10, 21, 8, 0), [[]], ended=datetime(2026, 10, 21, 8, 30)),
)


def ids(result: dict) -> list[int]:
    return [row["session_id"] for row in result["sessions"]]


# -- list_sessions -------------------------------------------------------------------------


def test_sessions_are_listed_newest_first_with_their_details() -> None:
    result = ListSessionsTool(SESSIONS, NAMES, clock).run({})
    assert (result["total_matching"], result["returned"]) == (3, 3)
    assert ids(result) == [3, 2, 1]
    assert result["sessions"][1] == {
        "session_id": 2, "exercise": "Squat", "exercise_key": "squat",
        "started": "2026-10-20 09:30", "reps": 2, "clean_reps": 2,
        "saved_to_progress": {"reps": 12, "weight_kg": 40.0},
    }
    assert result["sessions"][0]["minutes"] == 30.0


def test_sessions_can_be_filtered() -> None:
    tool = ListSessionsTool(SESSIONS, NAMES, clock)
    assert ids(tool.run({"exercise": "Bench Press"})) == [3]
    assert ids(tool.run({"days": 2})) == [3, 2]
    assert ids(tool.run({"start_date": "2026-10-16", "end_date": "2026-10-20"})) == [2]
    assert ids(tool.run({"saved_to_progress_only": True})) == [2]
    limited = tool.run({"limit": 1})
    assert (limited["total_matching"], limited["returned"], ids(limited)) == (3, 1, [3])


def test_a_bad_exercise_is_reported_to_the_model() -> None:
    with pytest.raises(ToolArgumentError, match="Unknown exercise"):
        ListSessionsTool(SESSIONS, NAMES, clock).run({"exercise": "curls"})


# -- get_session -----------------------------------------------------------------------------


def test_a_session_is_shown_rep_by_rep() -> None:
    sessions = FakeSessions(stored(
        5, "squat", datetime(2026, 10, 20, 9, 30), [[], [("squat_depth", 118.44, 100.0)]]
    ))
    result = GetSessionTool(sessions).run({"session_id": 5})
    assert result["session"]["session_id"] == 5 and result["reps_omitted"] == 0
    clean, flawed = result["reps"]
    assert clean["issues"] == [] and clean["seconds"] == 2.0
    assert clean["measurements"] == {"knee_angle": {"min": 95.0, "max": 170.0}}
    assert flawed["issues"] == [
        {"rule": "squat_depth", "message": "msg squat_depth", "measured": 118.4, "limit": 100.0}
    ]


def test_an_unknown_session_is_an_error() -> None:
    tool = GetSessionTool(SESSIONS)
    with pytest.raises(ToolArgumentError, match="No session with id 99"):
        tool.run({"session_id": 99})
    with pytest.raises(ToolArgumentError, match="required"):
        tool.run({})


# -- mistake_summary -------------------------------------------------------------------------


MISTAKES = FakeSessions(
    stored(1, "squat", datetime(2026, 10, 18, 9, 0),
           [[("squat_depth", 110.0, 105.0)], [("torso_lean", 60.0, 50.0)]]),
    stored(2, "squat", datetime(2026, 10, 20, 9, 0), [[], [("squat_depth", 120.0, 100.0)]]),
)


def test_mistakes_are_counted_across_sessions_most_frequent_first() -> None:
    result = MistakeSummaryTool(MISTAKES, NAMES, clock).run({})
    assert (result["sessions_analyzed"], result["reps_analyzed"], result["clean_reps"]) == (2, 4, 1)
    depth, lean = result["mistakes"]
    assert depth == {
        "exercise": "Squat", "rule": "squat_depth", "what": "msg squat_depth", "times": 2,
        "in_sessions": 2, "avg_measured": 115.0, "limit": 100.0, "last_seen": "2026-10-20",
    }
    assert (lean["rule"], lean["times"], lean["limit"], lean["last_seen"]) == (
        "torso_lean", 1, 50.0, "2026-10-18"
    )


def test_mistakes_respect_the_window_and_the_top_limit() -> None:
    tool = MistakeSummaryTool(MISTAKES, NAMES, clock)
    assert [m["rule"] for m in tool.run({"days": 2})["mistakes"]] == ["squat_depth"]
    assert len(tool.run({"top": 1})["mistakes"]) == 1
    assert tool.run({"exercise": "bench_press"})["mistakes"] == []


# -- progress_history ------------------------------------------------------------------------


def progress_set(session_id: int, day: int, hour: int, reps: int, weight: float | None) -> ProgressSet:
    return ProgressSet(session_id, "squat", "Squat", datetime(2026, 10, day, hour), reps, weight)


def test_progress_is_grouped_by_day_with_volume_and_bests() -> None:
    progress = FakeProgress(
        progress_set(1, 19, 10, 12, 40.0), progress_set(2, 19, 11, 10, 50.0),
        progress_set(3, 21, 10, 10, 60.0),
    )
    result = ProgressHistoryTool(progress, NAMES, clock).run({"exercise": "squat", "days": 7})
    assert (result["training_days"], result["sets"], result["volume_unit"]) == (2, 3, "kg")
    assert result["total_volume"] == 1580
    assert (result["heaviest_weight_kg"], result["most_reps_in_a_set"]) == (60.0, 12)
    assert result["days"][0] == {
        "date": "2026-10-19", "total_reps": 22, "volume": 980,
        "sets": [{"reps": 12, "weight_kg": 40.0}, {"reps": 10, "weight_kg": 50.0}],
    }
    assert "note" not in result


def test_progress_for_one_day_and_for_bodyweight_work() -> None:
    progress = FakeProgress(progress_set(1, 20, 9, 15, None), progress_set(2, 21, 9, 12, None))
    result = ProgressHistoryTool(progress, NAMES, clock).run({"exercise": "squat", "days": 1})
    assert (result["training_days"], result["volume_unit"], result["total_volume"]) == (1, "reps", 12)
    assert result["heaviest_weight_kg"] is None


def test_an_empty_range_says_so() -> None:
    result = ProgressHistoryTool(FakeProgress(), NAMES, clock).run({"exercise": "squat"})
    assert result["sets"] == 0 and "No sets" in result["note"] and result["days"] == []


def test_progress_needs_an_exercise() -> None:
    with pytest.raises(ToolArgumentError, match="required"):
        ProgressHistoryTool(FakeProgress(), NAMES, clock).run({})


# -- routines, exercises, wiring ---------------------------------------------------------------


def test_routines_are_listed_with_exercise_names() -> None:
    routines = FakeRoutines(Routine(1, "Push", ("bench_press", "gone")), Routine(2, "Legs", ("squat",)))
    assert ListRoutinesTool(routines, NAMES).run({}) == {
        "routines": [
            {"name": "Push", "exercises": ["Bench Press"]},
            {"name": "Legs", "exercises": ["Squat"]},
        ]
    }


def test_every_exercise_is_described_with_its_checks() -> None:
    catalog = catalog_for(AppConfig())
    exercises = ListExercisesTool(catalog).run({})["exercises"]
    assert [e["key"] for e in exercises] == list(catalog)
    squat = next(e for e in exercises if e["key"] == "squat")
    assert squat["camera_view"] == "side" and squat["counts"] == "reps"
    assert {c["rule"] for c in squat["checks"]} == {"squat_depth", "torso_lean"}
    assert all(c["why"] for e in exercises for c in e["checks"])
    assert next(e for e in exercises if e["key"] == "plank")["counts"] == "timed hold"


def test_tools_reject_unexpected_arguments() -> None:
    with pytest.raises(ToolArgumentError):
        ListRoutinesTool(FakeRoutines(), NAMES).run({"x": 1})


def test_the_default_tool_set_builds_a_working_registry(tmp_path: Path) -> None:
    catalog = catalog_for(AppConfig())
    registry = ToolRegistry(default_tools(catalog, SESSIONS, FakeProgress(), FakeRoutines(), clock))
    assert {s.name for s in registry.specs} == {
        "list_exercises", "list_sessions", "get_session",
        "mistake_summary", "progress_history", "list_routines",
    }
    for spec in registry.specs:
        assert spec.parameters["type"] == "object" and spec.description