from __future__ import annotations

from dataclasses import dataclass

from pose_tracker.application.session_controller import SessionReport


@dataclass(frozen=True, slots=True)
class RepRow:
    rep_number: int
    duration_s: float
    issues: tuple[str, ...]

    @property
    def is_clean(self) -> bool:
        return not self.issues


@dataclass(frozen=True, slots=True)
class MistakeTally:
    rule_id: str
    message: str
    explanation: str
    count: int
    rep_numbers: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class SummaryState:
    exercise_name: str
    total_reps: int
    clean_reps: int
    rows: tuple[RepRow, ...]
    mistakes: tuple[MistakeTally, ...]  # most frequent first

    @property
    def issue_reps(self) -> int:
        return self.total_reps - self.clean_reps

    @property
    def clean_percent(self) -> int:
        return round(100 * self.clean_reps / self.total_reps) if self.total_reps else 0


def build_summary(report: SessionReport) -> SummaryState:
    exercise = report.exercise
    rule_order = {rule.rule_id: index for index, rule in enumerate(exercise.rules)}

    messages: dict[str, str] = {}
    reps_by_rule: dict[str, list[int]] = {}
    rows = []
    for result in report.results:
        rows.append(
            RepRow(
                rep_number=result.rep_number,
                duration_s=result.rep.duration_ms / 1000,
                issues=tuple(v.message for v in result.violations),
            )
        )
        for violation in result.violations:
            messages.setdefault(violation.rule_id, violation.message)
            reps_by_rule.setdefault(violation.rule_id, []).append(result.rep_number)

    tallies = [
        MistakeTally(
            rule_id=rule_id,
            message=messages[rule_id],
            explanation=exercise.explanations.get(rule_id, ""),
            count=len(rep_numbers),
            rep_numbers=tuple(rep_numbers),
        )
        for rule_id, rep_numbers in reps_by_rule.items()
    ]
    tallies.sort(key=lambda t: (-t.count, rule_order.get(t.rule_id, len(rule_order))))

    return SummaryState(
        exercise_name=exercise.name,
        total_reps=report.total_reps,
        clean_reps=report.clean_reps,
        rows=tuple(rows),
        mistakes=tuple(tallies),
    )