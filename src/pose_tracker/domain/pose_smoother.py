from __future__ import annotations

from pose_tracker.domain.filters import OneEuroConfig, OneEuroFilter
from pose_tracker.domain.pose import Landmark, Pose


class PoseSmoother:
    """Smooths x, y, z of every landmark independently. Visibility passes through."""

    def __init__(self, config: OneEuroConfig) -> None:
        self._config = config
        self._filters: list[tuple[OneEuroFilter, OneEuroFilter, OneEuroFilter]] = []

    def smooth(self, pose: Pose, timestamp_ms: int) -> Pose:
        timestamp_s = timestamp_ms / 1000.0
        if len(self._filters) != len(pose.landmarks):
            self._filters = [
                (
                    OneEuroFilter(self._config),
                    OneEuroFilter(self._config),
                    OneEuroFilter(self._config),
                )
                for _ in pose.landmarks
            ]
        return Pose(
            landmarks=tuple(
                Landmark(
                    x=fx.filter(lm.x, timestamp_s),
                    y=fy.filter(lm.y, timestamp_s),
                    z=fz.filter(lm.z, timestamp_s),
                    visibility=lm.visibility,
                )
                for lm, (fx, fy, fz) in zip(pose.landmarks, self._filters)
            )
        )

    def reset(self) -> None:
        """Forget history, e.g. when the person leaves the frame."""
        self._filters = []