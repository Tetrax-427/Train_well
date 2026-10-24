from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pose_tracker.application.chat.tool_arguments import (
    Arguments,
    ToolArgumentError,
    resolve_exercise,
    time_window,
)
from pose_tracker.domain.chat import ToolSpec
from pose_tracker.domain.exercise import Exercise
from pose_tracker.domain.history import SessionSummary
from pose_tracker.domain.progress import build_chart_data
from pose_tracker.interfaces import ChatTool, ProgressReader, RoutineStore, SessionReader

Clock = Callable[[], datetime]

MAX_SESSIONS_LISTED = 50
MAX_SESSIONS_ANALYZED = 200
MAX_REPS_SHOWN = 100
MAX_PROGRESS_DAYS = 60

_WINDOW_PROPERTIES: dict[str, Any] = {
    "days": {
        "type": "integer",
        "description": "Only the last N days, today included. For example 7 = the last week.",
    },
    "start_date": {"type": "string", "description": "First day to include, as YYYY-MM-DD."},
    "end_date": {"type": "string", "description": "Last day to include, as YYYY-MM-DD."},
}
_WINDOW_NAMES = tuple(_WINDOW_PROPERTIES)


def _schema(properties: Mapping[str, Any], required: Sequence[str] = ()) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "object", "properties": dict(properties)}
    if required:
        schema["required"] = list(required)
    return schema


def _exercise_property(names: Mapping[str, str]) -> dict[str, Any]:
    return {"type": "string", "enum": list(names), "description": "Exercise key."}


def _round(value: float) -> float:
    return round(value, 1) if abs(value) >= 10 else round(value, 3)


def _when(moment: datetime) -> str:
    return f"{moment:%Y-%m-%d %H:%M}"


def _session_row(summary: SessionSummary) -> dict[str, Any]:
    row: dict[str, Any] = {
        "session_id": summary.session_id,
        "exercise": summary.exercise_name,
        "exercise_key": summary.exercise_key,
        "started": _when(summary.started_at),
        "reps": summary.total_reps,
        "clean_reps": summary.clean_reps,
        "saved_to_progress": None,
    }
    if summary.ended_at is not None:
        row["minutes"] = round((summary.ended_at - summary.started_at).total_seconds() / 60, 1)
    if summary.progress is not None:
        row["saved_to_progress"] = {
            "reps": summary.progress.reps,
            "weight_kg": summary.progress.weight_kg,
        }
    return row


class ListExercisesTool:
    def __init__(self, catalog: Mapping[str, Exercise]) -> None:
        self._catalog = catalog
        self.spec = ToolSpec(
            "list_exercises",
            "List the exercises the app can track, each with its camera view and the form "
            "checks it makes (rule ids with a short explanation of why each matters).",
            _schema({}),
        )

    def run(self, arguments: Mapping[str, Any]) -> Any:
        Arguments(arguments, ())
        return {
            "exercises": [
                {
                    "key": exercise.key,
                    "name": exercise.name,
                    "camera_view": exercise.required_view.name.lower(),
                    "counts": "timed hold" if exercise.timed else "reps",
                    "checks": [
                        {"rule": rule.rule_id, "why": exercise.explanations.get(rule.rule_id, "")}
                        for rule in exercise.rules
                    ],
                }
                for exercise in self._catalog.values()
            ]
        }


class ListSessionsTool:
    def __init__(self, reader: SessionReader, names: Mapping[str, str], clock: Clock) -> None:
        self._reader, self._names, self._clock = reader, dict(names), clock
        self.spec = ToolSpec(
            "list_sessions",
            "List the user's training sessions, newest first. One session is one set of one "
            "exercise (one Start to Stop). Filter by exercise and date range.",
            _schema({
                "exercise": _exercise_property(self._names),
                **_WINDOW_PROPERTIES,
                "saved_to_progress_only": {
                    "type": "boolean",
                    "description": "Only sessions saved to progress (they carry a weight).",
                },
                "limit": {"type": "integer", "description": f"Rows to return, up to {MAX_SESSIONS_LISTED}. Default 20."},
            }),
        )

    def run(self, arguments: Mapping[str, Any]) -> Any:
        args = Arguments(arguments, ("exercise", *_WINDOW_NAMES, "saved_to_progress_only", "limit"))
        key = resolve_exercise(args.text("exercise"), self._names)
        window = time_window(args, self._clock().date())
        saved_only = args.boolean("saved_to_progress_only")
        limit = args.integer("limit", 1, MAX_SESSIONS_LISTED, default=20) or 20
        matching = [
            s for s in self._reader.list_sessions(key)
            if window.contains(s.started_at) and (not saved_only or s.progress is not None)
        ]
        shown = matching[:limit]
        return {
            "total_matching": len(matching),
            "returned": len(shown),
            "sessions": [_session_row(s) for s in shown],
        }


class GetSessionTool:
    def __init__(self, reader: SessionReader) -> None:
        self._reader = reader
        self.spec = ToolSpec(
            "get_session",
            "One session in detail: every rep with its duration, measured ranges (angles in "
            "degrees, distances in torso lengths) and the form mistakes found in it.",
            _schema(
                {"session_id": {"type": "integer", "description": "Id from list_sessions."}},
                required=["session_id"],
            ),
        )

    def run(self, arguments: Mapping[str, Any]) -> Any:
        args = Arguments(arguments, ("session_id",))
        session_id = args.require_integer("session_id", 1, 10**9)
        stored = self._reader.get_session(session_id)
        if stored is None:
            raise ToolArgumentError(f"No session with id {session_id}.")
        return {
            "session": _session_row(stored.summary),
            "reps_omitted": max(len(stored.reps) - MAX_REPS_SHOWN, 0),
            "reps": [
                {
                    "rep": rep.rep_number,
                    "seconds": round(rep.duration_ms / 1000, 1),
                    "measurements": {
                        name: {"min": _round(low), "max": _round(high)}
                        for name, (low, high) in rep.feature_ranges.items()
                    },
                    "issues": [
                        {
                            "rule": v.rule_id,
                            "message": v.message,
                            "measured": _round(v.measured),
                            "limit": _round(v.limit),
                        }
                        for v in rep.violations
                    ],
                }
                for rep in stored.reps[:MAX_REPS_SHOWN]
            ],
        }


@dataclass(slots=True)
class _Tally:
    exercise: str
    rule_id: str
    message: str
    latest_limit: float
    last_seen: datetime
    count: int = 0
    measured_sum: float = 0.0
    session_ids: set[int] = field(default_factory=set)


class MistakeSummaryTool:
    def __init__(self, reader: SessionReader, names: Mapping[str, str], clock: Clock) -> None:
        self._reader, self._names, self._clock = reader, dict(names), clock
        self.spec = ToolSpec(
            "mistake_summary",
            "Which form mistakes the user makes most, counted across sessions. Each row gives "
            "how often, in how many sessions, the average measured value against the limit, "
            "and when it was last seen. Filter by exercise and date range.",
            _schema({
                "exercise": _exercise_property(self._names),
                **_WINDOW_PROPERTIES,
                "top": {"type": "integer", "description": "How many mistakes to return, up to 30. Default 10."},
            }),
        )

    def run(self, arguments: Mapping[str, Any]) -> Any:
        args = Arguments(arguments, ("exercise", *_WINDOW_NAMES, "top"))
        key = resolve_exercise(args.text("exercise"), self._names)
        window = time_window(args, self._clock().date())
        top = args.integer("top", 1, 30, default=10) or 10

        matching = [s for s in self._reader.list_sessions(key) if window.contains(s.started_at)]
        analyzed = matching[:MAX_SESSIONS_ANALYZED]  # newest first
        tallies: dict[tuple[str, str], _Tally] = {}
        reps = clean = 0
        for summary in analyzed:
            stored = self._reader.get_session(summary.session_id)
            if stored is None:
                continue
            reps += summary.total_reps
            clean += summary.clean_reps
            for rep in stored.reps:
                for v in rep.violations:
                    tally = tallies.setdefault(
                        (summary.exercise_key, v.rule_id),
                        _Tally(summary.exercise_name, v.rule_id, v.message, v.limit, summary.started_at),
                    )
                    tally.count += 1
                    tally.measured_sum += v.measured
                    tally.session_ids.add(summary.session_id)
        ranked = sorted(tallies.values(), key=lambda t: (-t.count, t.exercise, t.rule_id))
        return {
            "sessions_analyzed": len(analyzed),
            "older_sessions_skipped": len(matching) - len(analyzed),
            "reps_analyzed": reps,
            "clean_reps": clean,
            "mistakes": [
                {
                    "exercise": t.exercise,
                    "rule": t.rule_id,
                    "what": t.message,
                    "times": t.count,
                    "in_sessions": len(t.session_ids),
                    "avg_measured": _round(t.measured_sum / t.count),
                    "limit": _round(t.latest_limit),
                    "last_seen": f"{t.last_seen:%Y-%m-%d}",
                }
                for t in ranked[:top]
            ],
        }


class ProgressHistoryTool:
    def __init__(self, reader: ProgressReader, names: Mapping[str, str], clock: Clock) -> None:
        self._reader, self._names, self._clock = reader, dict(names), clock
        self.spec = ToolSpec(
            "progress_history",
            "The sets the user saved to progress for one exercise: per training day the reps "
            "and weight of every set, plus daily volume (sum of weight x reps, or total reps "
            "for bodyweight exercises) and bests.",
            _schema({"exercise": _exercise_property(self._names), **_WINDOW_PROPERTIES}, ["exercise"]),
        )

    def run(self, arguments: Mapping[str, Any]) -> Any:
        args = Arguments(arguments, ("exercise", *_WINDOW_NAMES))
        key = resolve_exercise(args.text("exercise"), self._names)
        if key is None:
            raise ToolArgumentError("'exercise' is required.")
        window = time_window(args, self._clock().date())
        sets = [
            s for s in self._reader.list_progress_sets(key, window.since)
            if window.contains(s.performed_at)
        ]
        data = build_chart_data(sets)
        days = [
            {
                "date": day.day.isoformat(),
                "sets": [{"reps": s.reps, "weight_kg": s.weight_kg} for s in day.sets],
                "total_reps": day.total_reps,
                "volume": _round(volume),
            }
            for day, volume in zip(data.days, data.volumes, strict=True)
        ]
        weights = [s.weight_kg for s in sets if s.weight_kg is not None]
        result: dict[str, Any] = {
            "exercise": self._names[key],
            "training_days": len(days),
            "sets": len(sets),
            "volume_unit": data.volume_unit,
            "total_volume": _round(sum(data.volumes)),
            "heaviest_weight_kg": max(weights) if weights else None,
            "most_reps_in_a_set": max((s.reps for s in sets), default=None),
            "older_days_omitted": max(len(days) - MAX_PROGRESS_DAYS, 0),
            "days": days[-MAX_PROGRESS_DAYS:],
        }
        if not sets:
            result["note"] = "No sets were saved to progress in this range."
        return result


class ListRoutinesTool:
    def __init__(self, store: RoutineStore, names: Mapping[str, str]) -> None:
        self._store, self._names = store, dict(names)
        self.spec = ToolSpec(
            "list_routines",
            "The user's saved routines (named, ordered lists of exercises such as Push day).",
            _schema({}),
        )

    def run(self, arguments: Mapping[str, Any]) -> Any:
        Arguments(arguments, ())
        return {
            "routines": [
                {
                    "name": routine.name,
                    "exercises": [self._names[k] for k in routine.exercise_keys if k in self._names],
                }
                for routine in self._store.list_routines()
            ]
        }


def default_tools(
    catalog: Mapping[str, Exercise],
    sessions: SessionReader,
    progress: ProgressReader,
    routines: RoutineStore,
    clock: Clock,
) -> list[ChatTool]:
    names = {key: exercise.name for key, exercise in catalog.items()}
    return [
        ListExercisesTool(catalog),
        ListSessionsTool(sessions, names, clock),
        GetSessionTool(sessions),
        MistakeSummaryTool(sessions, names, clock),
        ProgressHistoryTool(progress, names, clock),
        ListRoutinesTool(routines, names),
    ]