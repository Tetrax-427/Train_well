from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from pose_tracker.domain.geometry import distance, midpoint, to_point
from pose_tracker.domain.pose import LandmarkId, Pose


class CameraView(Enum):
    FRONT = auto()
    SIDE = auto()
    ANGLED = auto()   # between front and side; unreliable for angle measurement
    UNKNOWN = auto()  # torso not reliably visible


@dataclass(frozen=True, slots=True)
class ViewThresholds:
    """Bounds on shoulder-width / torso-length. Tune against real footage."""

    front_min_ratio: float = 0.55
    side_max_ratio: float = 0.30
    min_visibility: float = 0.5

    def __post_init__(self) -> None:
        if not 0 < self.side_max_ratio < self.front_min_ratio:
            raise ValueError("Require 0 < side_max_ratio < front_min_ratio")


_TORSO_IDS = (
    LandmarkId.LEFT_SHOULDER,
    LandmarkId.RIGHT_SHOULDER,
    LandmarkId.LEFT_HIP,
    LandmarkId.RIGHT_HIP,
)


def shoulder_to_torso_ratio(
    pose: Pose, aspect_ratio: float, min_visibility: float
) -> float | None:
    """Shoulder width divided by torso length in the image plane.

    Returns None if any torso landmark is not visible enough.
    """
    landmarks = [pose.get(i) for i in _TORSO_IDS]
    if any(lm.visibility < min_visibility for lm in landmarks):
        return None
    l_shoulder, r_shoulder, l_hip, r_hip = (to_point(lm, aspect_ratio) for lm in landmarks)
    torso_length = distance(midpoint(l_shoulder, r_shoulder), midpoint(l_hip, r_hip))
    if torso_length == 0.0:
        return None
    return distance(l_shoulder, r_shoulder) / torso_length


class ViewDetector:
    """Stateless, per-frame classification of the camera view."""

    def __init__(self, thresholds: ViewThresholds = ViewThresholds()) -> None:
        self._thresholds = thresholds

    def detect(self, pose: Pose, aspect_ratio: float) -> CameraView:
        ratio = shoulder_to_torso_ratio(pose, aspect_ratio, self._thresholds.min_visibility)
        if ratio is None:
            return CameraView.UNKNOWN
        if ratio >= self._thresholds.front_min_ratio:
            return CameraView.FRONT
        if ratio <= self._thresholds.side_max_ratio:
            return CameraView.SIDE
        return CameraView.ANGLED


class StableViewDetector:
    """Switches view only after ``frames_to_switch`` consecutive agreeing frames."""

    def __init__(self, detector: ViewDetector, frames_to_switch: int = 8) -> None:
        if frames_to_switch < 1:
            raise ValueError("frames_to_switch must be >= 1")
        self._detector = detector
        self._frames_to_switch = frames_to_switch
        self._current = CameraView.UNKNOWN
        self._pending: CameraView | None = None
        self._pending_count = 0

    @property
    def view(self) -> CameraView:
        return self._current

    def update(self, pose: Pose | None, aspect_ratio: float) -> CameraView:
        observed = (
            CameraView.UNKNOWN if pose is None else self._detector.detect(pose, aspect_ratio)
        )
        if observed is self._current:
            self._pending, self._pending_count = None, 0
            return self._current

        if observed is self._pending:
            self._pending_count += 1
        else:
            self._pending, self._pending_count = observed, 1

        if self._pending_count >= self._frames_to_switch:
            self._current = observed
            self._pending, self._pending_count = None, 0
        return self._current