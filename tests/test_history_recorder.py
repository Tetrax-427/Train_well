from __future__ import annotations

from datetime import datetime

import pytest

from pose_tracker.application.composite_recorder import CompositeRepRecorder
from pose_tracker.application.exercise_analyzer import RepResult
from pose_tracker.application.history_recorder import HistoryRepRecorder
from pose_tracker.domain.exercises.squat import build_squat
from pose_tracker.domain.features import BodyFeatures
from pose_tracker.domain.form import FormViolation
from pose_tracker.domain.history import RepRecord
from pose_tracker.domain.pose import Pose
from pose_tracker.domain.rep import Rep, Sample
from pose_tracker.errors import PersistenceError

SQUAT = build_squat()
T0, T1, T2 = (datetime(2026, 10, 15, 15, 30, s) for s in (0, 20, 50))


class FakeWriter:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.started: list[tuple[str, str, datetime]] = []
        self.reps: list[tuple[int, RepRecord]] = []
        self.finished: list[tuple[int, datetime]] = []

    def start_session(self, exercise_key: str, exercise_name: str, started_at: datetime) -> int:
        if self.fail:
            raise PersistenceError("boom")
        self.started.append((exercise_key, exercise_name, started_at))
        return 7

    def add_rep(self, session_id: int, rep: RepRecord) -> None:
        self.reps.append((session_id, rep))

    def finish_session(self, session_id: int, ended_at: datetime) -> None:
        self.finished.append((session_id, ended_at))


class FakeSnapshots:
    def nearest(self, timestamp_ms: int) -> bytes | None:
        return f"jpg-{timestamp_ms}".encode()


def make_result(violations: tuple[FormViolation, ...] = ()) -> RepResult:
    samples = tuple(
        Sample(i * 100, Pose(()), BodyFeatures(knee, lean))
        for i, (knee, lean) in enumerate([(170.0, 10.0), (95.0, 30.0), (172.0, 12.0)])
    )
    return RepResult(1, Rep(samples), violations)


def depth_violation() -> FormViolation:
    return FormViolation("squat_depth", "Go deeper", 118.4, 100.0, 100, Pose(()))


def make_recorder(writer: FakeWriter, times: list[datetime]) -> HistoryRepRecorder:
    iterator = iter(times)
    return HistoryRepRecorder(writer, FakeSnapshots(), clock=lambda: next(iterator))


def test_no_reps_means_no_session() -> None:
    writer = FakeWriter()
    recorder = make_recorder(writer, [T0, T2])
    recorder.close()
    assert writer.started == [] and writer.finished == []
    assert recorder.session_id is None


def test_session_starts_on_the_first_rep_with_the_creation_time() -> None:
    writer = FakeWriter()
    recorder = make_recorder(writer, [T0, T1, T2])
    recorder.record(SQUAT, make_result())
    assert writer.started == [("squat", "Squat", T0)]
    assert writer.reps[0][0] == 7
    assert writer.reps[0][1].recorded_at == T1
    assert recorder.session_id == 7


def test_rep_record_carries_explanation_snapshot_pose_and_ranges() -> None:
    writer = FakeWriter()
    recorder = make_recorder(writer, [T0, T1, T2])
    recorder.record(SQUAT, make_result((depth_violation(),)))

    record = writer.reps[0][1]
    assert record.duration_ms == 200
    assert record.feature_ranges == {"knee_angle": (95.0, 172.0), "torso_lean_deg": (10.0, 30.0)}
    [violation] = record.violations
    assert violation.rule_id == "squat_depth"
    assert violation.explanation == SQUAT.explanations["squat_depth"]
    assert violation.snapshot_jpeg == b"jpg-100"
    assert violation.measured == 118.4 and violation.limit == 100.0


def test_clean_rep_has_no_violations() -> None:
    writer = FakeWriter()
    make_recorder(writer, [T0, T1]).record(SQUAT, make_result())
    assert writer.reps[0][1].violations == ()


def test_persistence_failure_does_not_raise() -> None:
    recorder = make_recorder(FakeWriter(fail=True), [T0, T1])
    recorder.record(SQUAT, make_result())
    assert recorder.session_id is None


def test_close_finishes_the_session_once() -> None:
    writer = FakeWriter()
    recorder = make_recorder(writer, [T0, T1, T2, T2])
    recorder.record(SQUAT, make_result())
    recorder.close()
    recorder.close()
    assert writer.finished == [(7, T2)]


class Spy:
    def __init__(self, name: str, log: list[tuple[str, str]], fail_on_close: bool = False) -> None:
        self._name, self._log, self._fail = name, log, fail_on_close

    def record(self, exercise: object, result: object) -> None:
        self._log.append(("record", self._name))

    def close(self) -> None:
        self._log.append(("close", self._name))
        if self._fail:
            raise RuntimeError("close failed")


def test_composite_forwards_records_in_order() -> None:
    log: list[tuple[str, str]] = []
    CompositeRepRecorder(Spy("a", log), Spy("b", log)).record(SQUAT, make_result())
    assert log == [("record", "a"), ("record", "b")]


def test_composite_closes_every_recorder_even_if_one_fails() -> None:
    log: list[tuple[str, str]] = []
    composite = CompositeRepRecorder(Spy("a", log, fail_on_close=True), Spy("b", log))
    with pytest.raises(RuntimeError):
        composite.close()
    assert sorted(log) == [("close", "a"), ("close", "b")]