from __future__ import annotations

from pose_tracker.domain.frame import Frame
from pose_tracker.domain.pose import Pose
from pose_tracker.domain.pose_smoother import PoseSmoother
from pose_tracker.interfaces import PoseEstimator


class SmoothedPoseEstimator:
    """Decorator: temporally smooths the output of any PoseEstimator."""

    def __init__(self, inner: PoseEstimator, smoother: PoseSmoother) -> None:
        self._inner = inner
        self._smoother = smoother

    def estimate(self, frame: Frame) -> Pose | None:
        pose = self._inner.estimate(frame)
        if pose is None:
            self._smoother.reset()  # avoid blending stale positions after re-entry
            return None
        return self._smoother.smooth(pose, frame.timestamp_ms)

    def close(self) -> None:
        self._inner.close()