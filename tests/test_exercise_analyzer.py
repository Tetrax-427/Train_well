from __future__ import annotations

from pose_factory import squat_pose

from pose_tracker.application.exercise_analyzer import AnalysisStatus, ExerciseAnalyzer
from pose_tracker.domain.exercises.squat import build_squat
from pose_tracker.domain.view import StableViewDetector, ViewDetector

STANDING = [175] * 3
DESCENT = list(range(170, 85, -5))   # down to 90 degrees
ASCENT = list(range(90, 176, 5))
SHALLOW_DESCENT = list(range(170, 125, -5))  # only down to 130
SHALLOW_ASCENT = list(range(130, 176, 5))


def make_analyzer() -> ExerciseAnalyzer:
    detector = StableViewDetector(ViewDetector(), frames_to_switch=1)
    return ExerciseAnalyzer(build_squat(), detector)


def run(
    analyzer: ExerciseAnalyzer, knees: list[float], lean: float = 10.0, gap: float = 0.0
) -> AnalysisStatus:
    status = None
    for i, knee in enumerate(knees):
        status = analyzer.update(squat_pose(knee, lean, gap), i * 100, 1.0)
    assert status is not None
    return status


def test_good_squat_counts_one_clean_rep() -> None:
    analyzer = make_analyzer()
    status = run(analyzer, STANDING + DESCENT + ASCENT)
    assert status.rep_count == 1
    assert analyzer.results[0].is_clean


def test_shallow_squat_flags_depth() -> None:
    analyzer = make_analyzer()
    run(analyzer, STANDING + SHALLOW_DESCENT + SHALLOW_ASCENT)
    violations = analyzer.results[0].violations
    assert [v.rule_id for v in violations] == ["squat_depth"]


def test_forward_lean_is_flagged() -> None:
    analyzer = make_analyzer()
    run(analyzer, STANDING + DESCENT + ASCENT, lean=70.0)
    assert [v.rule_id for v in analyzer.results[0].violations] == ["torso_lean"]


def test_wrong_view_is_not_counted() -> None:
    analyzer = make_analyzer()
    status = run(analyzer, STANDING + DESCENT + ASCENT, gap=0.3)  # front view
    assert status.rep_count == 0
    assert not status.view_ok


def test_losing_the_person_discards_the_rep_in_progress() -> None:
    analyzer = make_analyzer()
    run(analyzer, STANDING + DESCENT)
    analyzer.update(None, 5000, 1.0)
    status = run(analyzer, ASCENT)
    assert status.rep_count == 0

class FakeRecorder:
    def __init__(self) -> None:
        self.recorded: list = []

    def record(self, exercise, result) -> None:
        self.recorded.append(result)

    def close(self) -> None: ...


def test_each_finished_rep_is_recorded() -> None:
    recorder = FakeRecorder()
    detector = StableViewDetector(ViewDetector(), frames_to_switch=1)
    analyzer = ExerciseAnalyzer(build_squat(), detector, recorder=recorder)
    run(analyzer, STANDING + DESCENT + ASCENT)
    assert [r.rep_number for r in recorder.recorded] == [1]