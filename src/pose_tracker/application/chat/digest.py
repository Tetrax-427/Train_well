from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import datetime

from pose_tracker.application.chat.budget import MAX_DIGEST_CHARS
from pose_tracker.application.chat.tools import (
    ListRoutinesTool,
    ListSessionsTool,
    MistakeSummaryTool,
    ProgressHistoryTool,
)
from pose_tracker.domain.progress import format_value
from pose_tracker.errors import PersistenceError
from pose_tracker.interfaces import ProgressReader, RoutineStore, SessionReader

logger = logging.getLogger(__name__)

RECENT_DAYS = 14
MISTAKE_DAYS = 30
PROGRESS_DAYS = 90
MAX_RECENT_LINES = 30
MAX_MISTAKES = 8

_HEADER = "TRAINING SUMMARY (read from the app's data just now)"
_SHORTENED = "(list shortened)"
# Share of the budget for: recent sessions, mistakes, progress, routines. Room a section
# does not use passes on to the next one.
_SHARES = (0.35, 0.40, 0.20, 0.05)


class TrainingDigest:
    """A short text summary of the user's training, for the start of the prompt.

    Small local models often do not call tools, so the facts that matter most are handed
    to them up front. It reuses the chat tools, so the two always agree.
    """

    def __init__(
        self,
        names: Mapping[str, str],
        sessions: SessionReader,
        progress: ProgressReader,
        routines: RoutineStore,
        clock: Callable[[], datetime],
    ) -> None:
        self._names = dict(names)
        self._sessions = ListSessionsTool(sessions, names, clock)
        self._mistakes = MistakeSummaryTool(sessions, names, clock)
        self._progress = ProgressHistoryTool(progress, names, clock)
        self._routines = ListRoutinesTool(routines, names)

    def text(self, max_chars: int = MAX_DIGEST_CHARS) -> str:
        """The summary, at most ``max_chars`` long. Long sections are shortened, newest first."""
        sections = (
            self._section(self._recent),
            self._section(self._common_mistakes),
            self._section(self._progress_bests),
            self._section(self._routine_list),
        )
        total = max_chars - len(_HEADER) - 1
        body: list[str] = []
        carry = 0
        for section, share in zip(sections, _SHARES, strict=True):
            allowance = int(total * share) + carry
            room = allowance - (2 if body else 0)
            fitted = _fit(section, room)
            if fitted is None:
                carry = max(allowance, 0)
                continue
            carry = max(room - len(fitted), 0)
            body.append(fitted)
        return _HEADER + "\n" + "\n\n".join(body)

    @staticmethod
    def _section(build: Callable[[], str]) -> str:
        try:
            return build()
        except PersistenceError:
            logger.exception("Part of the training summary could not be read")
            return "(a part of the summary could not be read)"

    def _recent(self) -> str:
        result = self._sessions.run({"days": RECENT_DAYS, "limit": MAX_RECENT_LINES})
        rows = result["sessions"]
        if not rows:
            return f"Sessions: none in the last {RECENT_DAYS} days."
        lines = [f"Sessions in the last {RECENT_DAYS} days, newest first (one session = one set):"]
        for row in rows:
            saved = row["saved_to_progress"]
            extra = ""
            if saved is not None:
                if saved["weight_kg"] is not None:
                    extra = f"; saved {format_value(saved['weight_kg'])} kg x {saved['reps']}"
                else:
                    extra = f"; saved {saved['reps']} reps (bodyweight)"
            lines.append(
                f"- {row['started'][:10]} {row['exercise']}: {_reps(row['reps'])}, "
                f"{row['clean_reps']} clean{extra}"
            )
        older = result["total_matching"] - result["returned"]
        if older > 0:
            lines.append(f"- ...and {older} older session(s) in this period")
        return "\n".join(lines)

    def _common_mistakes(self) -> str:
        result = self._mistakes.run({"days": MISTAKE_DAYS, "top": MAX_MISTAKES})
        reps, clean = result["reps_analyzed"], result["clean_reps"]
        if reps == 0:
            return f"Form mistakes: no reps recorded in the last {MISTAKE_DAYS} days."
        if not result["mistakes"]:
            return f"Form mistakes: none in the last {MISTAKE_DAYS} days ({_reps(reps)}, all clean)."
        lines = [
            f"Most common form mistakes in the last {MISTAKE_DAYS} days "
            f"({_reps(reps)}, {clean} clean):"
        ]
        for m in result["mistakes"]:
            lines.append(
                f"- {m['exercise']}: {m['rule']} ({m['what']}) x{m['times']} in "
                f"{m['in_sessions']} session(s), average {format_value(m['avg_measured'])} vs "
                f"limit {format_value(m['limit'])}, last {m['last_seen']}"
            )
        return "\n".join(lines)

    def _progress_bests(self) -> str:
        lines: list[str] = []
        for key, name in self._names.items():
            result = self._progress.run({"exercise": key, "days": PROGRESS_DAYS})
            if not result["sets"]:
                continue
            latest = result["days"][-1]
            sets = ", ".join(
                f"{format_value(s['weight_kg'])} kg x {s['reps']}"
                if s["weight_kg"] is not None else f"{s['reps']} reps"
                for s in latest["sets"]
            )
            heaviest = result["heaviest_weight_kg"]
            best = f", heaviest {format_value(heaviest)} kg" if heaviest is not None else ""
            lines.append(
                f"- {name}: {result['training_days']} day(s), {result['sets']} set(s){best}, "
                f"most reps in a set {result['most_reps_in_a_set']}; "
                f"latest {latest['date']}: {sets}"
            )
        if not lines:
            return f"Progress: nothing saved to progress in the last {PROGRESS_DAYS} days."
        return f"Progress (sets the user saved, last {PROGRESS_DAYS} days):\n" + "\n".join(lines)

    def _routine_list(self) -> str:
        routines = self._routines.run({})["routines"]
        if not routines:
            return "Routines: none saved."
        return "Saved routines: " + "; ".join(
            f"{r['name']} ({', '.join(r['exercises'])})" for r in routines
        )


def _fit(section: str, room: int) -> str | None:
    """The section if it fits in ``room`` characters, else its heading and as many leading
    lines as fit. None if not even one line fits."""
    if len(section) <= room:
        return section
    lines = section.split("\n")
    kept, size = [lines[0]], len(lines[0])
    for line in lines[1:]:
        if size + 1 + len(line) > room:
            break
        kept.append(line)
        size += 1 + len(line)
    if len(kept) == 1:
        return None
    if size + 1 + len(_SHORTENED) <= room:
        kept.append(_SHORTENED)
    return "\n".join(kept)


def _reps(count: int) -> str:
    return f"{count} rep" if count == 1 else f"{count} reps"