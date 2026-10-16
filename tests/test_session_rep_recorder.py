from __future__ import annotations

from pose_tracker.application.composite_recorder import SessionRepRecorder
from pose_tracker.application.exercise_analyzer import RepResult
from pose_tracker.domain.exercises.squat import build_squat
from pose_tracker.domain.features import BodyFeatures
from pose_tracker.domain.pose import Pose
from pose_tracker.domain.rep import Rep, Sample


class Stub:
    def __init__(self, name: str, log: list[tuple[str, str]], session_id: int | None = None) -> None:
        self._name, self._log = name, log
        self.session_id = session_id

    def record(self, exercise: object, result: object) -> None:
        self._log.append(("record", self._name))

    def close(self) -> None:
        self._log.append(("close", self._name))


def test_reps_and_close_reach_every_recorder_and_the_id_comes_from_the_primary() -> None:
    log: list[tuple[str, str]] = []
    recorder = SessionRepRecorder(Stub("history", log, session_id=7), Stub("text", log))
    sample = Sample(0, Pose(()), BodyFeatures(None, None))

    recorder.record(build_squat(), RepResult(1, Rep((sample,)), ()))
    recorder.close()

    assert recorder.session_id == 7
    assert log == [
        ("record", "history"), ("record", "text"), ("close", "text"), ("close", "history"),
    ] or sorted(log) == sorted([
        ("record", "history"), ("record", "text"), ("close", "history"), ("close", "text"),
    ])