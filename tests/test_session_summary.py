from __future__ import annotations

from pose_tracker.application.exercise_analyzer import RepResult
from pose_tracker.application.session_controller import SessionReport
from pose_tracker.application.session_summary import build_summary
from pose_tracker.domain.exercises.squat import build_squat
from pose_tracker.domain.features import BodyFeatures
from pose_tracker.domain.form import FormViolation
from pose_tracker.domain.pose import Pose
from pose_tracker.domain.rep import Rep, Sample

SQUAT = build_squat()


def make_result(number: int, *rule_ids: str) -> RepResult:
    samples = tuple(Sample(i * 500, Pose(()), BodyFeatures(None, None)) for i in range(5))  # 2.0 s
    violations = tuple(
        FormViolation(rule, f"msg {rule}", 1.0, 2.0, 0, Pose(())) for rule in rule_ids
    )
    return RepResult(number, Rep(samples), violations)


def report(*results: RepResult) -> SessionReport:
    return SessionReport(SQUAT, results, session_id=None)


def test_totals_and_percentage() -> None:
    summary = build_summary(report(
        make_result(1), make_result(2, "squat_depth"),
        make_result(3, "squat_depth", "torso_lean"), make_result(4),
    ))
    assert summary.exercise_name == "Squat"
    assert (summary.total_reps, summary.clean_reps, summary.issue_reps) == (4, 2, 2)
    assert summary.clean_percent == 50


def test_mistakes_are_grouped_and_ordered_by_frequency() -> None:
    summary = build_summary(report(
        make_result(1), make_result(2, "squat_depth"), make_result(3, "squat_depth", "torso_lean"),
    ))
    first, second = summary.mistakes
    assert (first.rule_id, first.count, first.rep_numbers) == ("squat_depth", 2, (2, 3))
    assert first.message == "msg squat_depth"
    assert first.explanation == SQUAT.explanations["squat_depth"]
    assert (second.rule_id, second.count, second.rep_numbers) == ("torso_lean", 1, (3,))


def test_ties_follow_the_rule_order_of_the_exercise() -> None:
    summary = build_summary(report(make_result(1, "torso_lean"), make_result(2, "squat_depth")))
    assert [m.rule_id for m in summary.mistakes] == ["squat_depth", "torso_lean"]


def test_rows_describe_each_rep() -> None:
    summary = build_summary(report(make_result(1), make_result(2, "squat_depth")))
    clean, flawed = summary.rows
    assert clean.is_clean and clean.duration_s == 2.0
    assert flawed.issues == ("msg squat_depth",) and not flawed.is_clean


def test_empty_session() -> None:
    summary = build_summary(report())
    assert summary.total_reps == 0 and summary.clean_percent == 0
    assert summary.rows == () and summary.mistakes == ()