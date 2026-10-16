from __future__ import annotations

from pose_tracker.domain.pose import Landmark, LandmarkId, Pose


def _midpoint(a: Landmark, b: Landmark) -> Landmark:
    """Midpoint of two landmarks; visibility is the weaker of the two."""
    return Landmark(
        x=(a.x + b.x) / 2,
        y=(a.y + b.y) / 2,
        z=(a.z + b.z) / 2,
        visibility=min(a.visibility, b.visibility),
    )


def with_derived_landmarks(pose: Pose) -> Pose:
    """Return a new Pose with NECK and MOUTH_CENTER appended."""
    if len(pose.landmarks) != LandmarkId.NECK:
        raise ValueError(
            f"Expected {LandmarkId.NECK} base landmarks, got {len(pose.landmarks)}"
        )
    neck = _midpoint(
        pose.get(LandmarkId.LEFT_SHOULDER), pose.get(LandmarkId.RIGHT_SHOULDER)
    )
    mouth_center = _midpoint(
        pose.get(LandmarkId.MOUTH_LEFT), pose.get(LandmarkId.MOUTH_RIGHT)
    )
    return Pose(landmarks=(*pose.landmarks, neck, mouth_center))