from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class LandmarkId(IntEnum):
    NOSE = 0
    LEFT_EYE_INNER = 1
    LEFT_EYE = 2
    LEFT_EYE_OUTER = 3
    RIGHT_EYE_INNER = 4
    RIGHT_EYE = 5
    RIGHT_EYE_OUTER = 6
    LEFT_EAR = 7
    RIGHT_EAR = 8
    MOUTH_LEFT = 9
    MOUTH_RIGHT = 10
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_ELBOW = 13
    RIGHT_ELBOW = 14
    LEFT_WRIST = 15
    RIGHT_WRIST = 16
    LEFT_PINKY = 17
    RIGHT_PINKY = 18
    LEFT_INDEX = 19
    RIGHT_INDEX = 20
    LEFT_THUMB = 21
    RIGHT_THUMB = 22
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28
    LEFT_HEEL = 29
    RIGHT_HEEL = 30
    LEFT_FOOT_INDEX = 31  # toe
    RIGHT_FOOT_INDEX = 32  # toe
    NECK = 33
    MOUTH_CENTER = 34


@dataclass(frozen=True, slots=True)
class Landmark:
    """Normalized coordinates: x, y in [0, 1] of the image, z is relative depth."""

    x: float
    y: float
    z: float
    visibility: float


@dataclass(frozen=True, slots=True)
class Pose:
    landmarks: tuple[Landmark, ...]

    def get(self, landmark_id: LandmarkId) -> Landmark:
        return self.landmarks[landmark_id]


_L = LandmarkId

SKELETON: tuple[tuple[LandmarkId, LandmarkId], ...] = (
    # Head
    (_L.LEFT_EAR, _L.LEFT_EYE_OUTER), (_L.LEFT_EYE_OUTER, _L.LEFT_EYE),
    (_L.LEFT_EYE, _L.LEFT_EYE_INNER), (_L.LEFT_EYE_INNER, _L.NOSE),
    (_L.NOSE, _L.RIGHT_EYE_INNER), (_L.RIGHT_EYE_INNER, _L.RIGHT_EYE),
    (_L.RIGHT_EYE, _L.RIGHT_EYE_OUTER), (_L.RIGHT_EYE_OUTER, _L.RIGHT_EAR),
    (_L.MOUTH_LEFT, _L.MOUTH_RIGHT),
    # Torso
    (_L.LEFT_SHOULDER, _L.RIGHT_SHOULDER), (_L.LEFT_HIP, _L.RIGHT_HIP),
    (_L.LEFT_SHOULDER, _L.LEFT_HIP), (_L.RIGHT_SHOULDER, _L.RIGHT_HIP),
    # Neck
    (_L.LEFT_SHOULDER, _L.NECK), (_L.RIGHT_SHOULDER, _L.NECK),
    (_L.NECK, _L.MOUTH_CENTER),
    # Arms
    (_L.LEFT_SHOULDER, _L.LEFT_ELBOW), (_L.LEFT_ELBOW, _L.LEFT_WRIST),
    (_L.RIGHT_SHOULDER, _L.RIGHT_ELBOW), (_L.RIGHT_ELBOW, _L.RIGHT_WRIST),
    # Hands
    (_L.LEFT_WRIST, _L.LEFT_PINKY), (_L.LEFT_WRIST, _L.LEFT_INDEX),
    (_L.LEFT_WRIST, _L.LEFT_THUMB), (_L.LEFT_PINKY, _L.LEFT_INDEX),
    (_L.RIGHT_WRIST, _L.RIGHT_PINKY), (_L.RIGHT_WRIST, _L.RIGHT_INDEX),
    (_L.RIGHT_WRIST, _L.RIGHT_THUMB), (_L.RIGHT_PINKY, _L.RIGHT_INDEX),
    # Legs
    (_L.LEFT_HIP, _L.LEFT_KNEE), (_L.LEFT_KNEE, _L.LEFT_ANKLE),
    (_L.RIGHT_HIP, _L.RIGHT_KNEE), (_L.RIGHT_KNEE, _L.RIGHT_ANKLE),
    # Feet
    (_L.LEFT_ANKLE, _L.LEFT_HEEL), (_L.LEFT_HEEL, _L.LEFT_FOOT_INDEX),
    (_L.LEFT_ANKLE, _L.LEFT_FOOT_INDEX),
    (_L.RIGHT_ANKLE, _L.RIGHT_HEEL), (_L.RIGHT_HEEL, _L.RIGHT_FOOT_INDEX),
    (_L.RIGHT_ANKLE, _L.RIGHT_FOOT_INDEX),
)