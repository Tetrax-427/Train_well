from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from pose_tracker.domain.pose import LandmarkId, Pose


class BodySide(Enum):
    LEFT = auto()
    RIGHT = auto()


@dataclass(frozen=True, slots=True)
class SideLandmarks:
    shoulder: LandmarkId
    elbow: LandmarkId
    wrist: LandmarkId
    hip: LandmarkId
    knee: LandmarkId
    ankle: LandmarkId
    heel: LandmarkId
    toe: LandmarkId

    def tracked(self) -> tuple[LandmarkId, ...]:
        """Landmarks used to judge how well this side is visible."""
        return (self.shoulder, self.elbow, self.wrist, self.hip, self.knee, self.ankle)


_L = LandmarkId

LEFT_SIDE = SideLandmarks(
    _L.LEFT_SHOULDER, _L.LEFT_ELBOW, _L.LEFT_WRIST, _L.LEFT_HIP,
    _L.LEFT_KNEE, _L.LEFT_ANKLE, _L.LEFT_HEEL, _L.LEFT_FOOT_INDEX,
)
RIGHT_SIDE = SideLandmarks(
    _L.RIGHT_SHOULDER, _L.RIGHT_ELBOW, _L.RIGHT_WRIST, _L.RIGHT_HIP,
    _L.RIGHT_KNEE, _L.RIGHT_ANKLE, _L.RIGHT_HEEL, _L.RIGHT_FOOT_INDEX,
)


def landmarks_for(side: BodySide) -> SideLandmarks:
    return LEFT_SIDE if side is BodySide.LEFT else RIGHT_SIDE


def _mean_visibility(pose: Pose, ids: tuple[LandmarkId, ...]) -> float:
    return sum(pose.get(i).visibility for i in ids) / len(ids)


def select_visible_side(pose: Pose) -> BodySide:
    """The side whose limbs are better visible. Ties go to LEFT (deterministic)."""
    left = _mean_visibility(pose, LEFT_SIDE.tracked())
    right = _mean_visibility(pose, RIGHT_SIDE.tracked())
    return BodySide.RIGHT if right > left else BodySide.LEFT