from __future__ import annotations

from pose_tracker.domain.derived import with_derived_landmarks
from pose_tracker.domain.frame import Frame
from pose_tracker.domain.pose import Pose
from pose_tracker.interfaces import PoseEstimator


class DerivedLandmarksEstimator:
    """Decorator: adds derived landmarks (neck, mouth center) to any PoseEstimator."""

    def __init__(self, inner: PoseEstimator) -> None:
        self._inner = inner

    def estimate(self, frame: Frame) -> Pose | None:
        pose = self._inner.estimate(frame)
        return None if pose is None else with_derived_landmarks(pose)

    def close(self) -> None:
        self._inner.close()