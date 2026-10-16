from __future__ import annotations

import numpy as np

from pose_tracker.application.fps import FpsMeter
from pose_tracker.application.pipeline import PosePipeline
from pose_tracker.domain.frame import Frame
from pose_tracker.domain.derived import with_derived_landmarks
from pose_tracker.domain.pose import Landmark, LandmarkId, Pose


class FakeSource:
    def __init__(self, count: int) -> None:
        self._remaining = count

    def read(self) -> Frame | None:
        if self._remaining == 0:
            return None
        self._remaining -= 1
        return Frame(np.zeros((4, 4, 3), dtype=np.uint8), timestamp_ms=self._remaining)

    def close(self) -> None: ...


class FakeEstimator:
    def __init__(self) -> None:
        self.calls = 0

    def estimate(self, frame: Frame) -> None:
        self.calls += 1
        return None

    def close(self) -> None: ...


class FakeAnalyzer:
    def analyze(self, pose, timestamp_ms, aspect_ratio):
        return ()


class FakeRenderer:
    def render(self, image, pose, fps, status_lines=()):
        return image


class FakeDisplay:
    def __init__(self, stop_after: int | None = None) -> None:
        self.shown = 0
        self._stop_after = stop_after

    def show(self, image) -> bool:
        self.shown += 1
        return self._stop_after is None or self.shown < self._stop_after

    def close(self) -> None: ...


def _pipeline(source, estimator, display) -> PosePipeline:
    return PosePipeline(source, estimator, FakeAnalyzer(), FakeRenderer(), display, FpsMeter())

def test_runs_until_source_is_exhausted() -> None:
    estimator, display = FakeEstimator(), FakeDisplay()
    _pipeline(FakeSource(3), estimator, display).run()
    assert estimator.calls == 3
    assert display.shown == 3


def test_stops_when_display_requests_quit() -> None:
    estimator, display = FakeEstimator(), FakeDisplay(stop_after=2)
    _pipeline(FakeSource(100), estimator, display).run()
    assert display.shown == 2


def test_neck_is_midpoint_of_shoulders() -> None:
    base = [Landmark(0.0, 0.0, 0.0, 1.0)] * LandmarkId.NECK
    base[LandmarkId.LEFT_SHOULDER] = Landmark(0.4, 0.5, 0.0, 0.9)
    base[LandmarkId.RIGHT_SHOULDER] = Landmark(0.6, 0.5, 0.0, 0.7)

    neck = with_derived_landmarks(Pose(tuple(base))).get(LandmarkId.NECK)

    assert neck.x == 0.5 and neck.y == 0.5
    assert neck.visibility == 0.7

class FakeObserver:
    def __init__(self) -> None:
        self.seen = 0

    def observe(self, frame: Frame) -> None:
        self.seen += 1


def test_observers_see_every_frame() -> None:
    observer = FakeObserver()
    PosePipeline(
        FakeSource(3), FakeEstimator(), FakeAnalyzer(), FakeRenderer(),
        FakeDisplay(), FpsMeter(), observers=(observer,),
    ).run()
    assert observer.seen == 3