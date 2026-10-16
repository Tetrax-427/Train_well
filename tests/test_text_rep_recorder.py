from __future__ import annotations

from datetime import datetime
from pathlib import Path
import dataclasses
from pose_tracker.application.exercise_analyzer import RepResult
from pose_tracker.domain.exercises.squat import build_squat
from pose_tracker.domain.features import BodyFeatures
from pose_tracker.domain.form import FormViolation
from pose_tracker.domain.pose import Pose
from pose_tracker.domain.rep import Rep, Sample
from pose_tracker.infrastructure.text_rep_recorder import TextFileRepRecorder

NOW = datetime(2026, 10, 15, 15, 30, 12)
SQUAT = build_squat()


def clock() -> datetime:
    return NOW


def make_result(number: int, violations: tuple[FormViolation, ...] = ()) -> RepResult:
    values = [(170.0, 10.0), (95.0, 30.0), (172.0, 12.0)]
    samples = tuple(
        Sample(i * 100, Pose(()), BodyFeatures(knee, lean))
        for i, (knee, lean) in enumerate(values)
    )
    return RepResult(number, Rep(samples), violations)


def depth_violation() -> FormViolation:
    return FormViolation("squat_depth", "Go deeper", 118.4, 100.0, 1500, Pose(()))


def test_no_reps_creates_no_file(tmp_path: Path) -> None:
    directory = tmp_path / "sessions"
    recorder = TextFileRepRecorder(directory, clock)
    recorder.close()
    assert not directory.exists()


def test_writes_header_reps_and_footer(tmp_path: Path) -> None:
    recorder = TextFileRepRecorder(tmp_path / "sessions", clock)
    recorder.record(SQUAT, make_result(1))
    recorder.record(SQUAT, make_result(2, (depth_violation(),)))
    recorder.close()

    assert recorder.path is not None
    assert recorder.path.name == "2026-10-15_153012_squat.txt"
    text = recorder.path.read_text(encoding="utf-8")
    assert "Exercise: Squat" in text
    assert "Rep 1 | 15:30:12 | 0.2s | clean" in text
    assert "Rep 2 | 15:30:12 | 0.2s | 1 issue(s)" in text
    assert "knee_angle: min 95.0, max 172.0" in text
    assert "torso_lean_deg: min 10.0, max 30.0" in text
    assert "! squat_depth: Go deeper (measured 118.4, limit 100.0, at 1.5s" in text
    assert "Total reps: 2 | clean: 1 | with issues: 1" in text


def test_reps_are_on_disk_before_close(tmp_path: Path) -> None:
    recorder = TextFileRepRecorder(tmp_path, clock)
    recorder.record(SQUAT, make_result(1))
    assert recorder.path is not None
    assert "Rep 1" in recorder.path.read_text(encoding="utf-8")
    recorder.close()


def test_close_is_idempotent(tmp_path: Path) -> None:
    recorder = TextFileRepRecorder(tmp_path, clock)
    recorder.record(SQUAT, make_result(1))
    recorder.close()
    recorder.close()


def test_write_failure_does_not_raise(tmp_path: Path) -> None:
    blocker = tmp_path / "not_a_directory"
    blocker.write_text("x")
    recorder = TextFileRepRecorder(blocker / "sessions", clock)
    recorder.record(SQUAT, make_result(1))  # must not raise
    recorder.close()

def test_only_selected_features_are_logged(tmp_path: Path) -> None:
    exercise = dataclasses.replace(SQUAT, logged_features=("knee_angle",))
    recorder = TextFileRepRecorder(tmp_path, clock)
    recorder.record(exercise, make_result(1))
    recorder.close()
    assert recorder.path is not None
    text = recorder.path.read_text(encoding="utf-8")
    assert "knee_angle" in text
    assert "torso_lean_deg" not in text