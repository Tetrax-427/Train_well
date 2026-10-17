from __future__ import annotations

from pose_tracker.domain.body_side import BodySide, landmarks_for
from pose_tracker.domain.pose import LandmarkId

# Which joints each rule is about, as roles on one side of the body.
_ROLES: dict[str, tuple[str, ...]] = {
    # squat
    "squat_depth": ("hip", "knee", "ankle"),
    "torso_lean": ("shoulder", "hip"),
    # shoulder press
    "press_bottom": ("shoulder", "elbow", "wrist"),
    "press_lockout": ("shoulder", "elbow", "wrist"),
    "layback": ("shoulder", "hip"),
    "bar_path": ("wrist",),
    "control": ("wrist",),
    "leg_drive": ("hip", "knee", "ankle"),
    # push-up
    "pushup_depth": ("shoulder", "elbow", "wrist"),
    "pushup_lockout": ("shoulder", "elbow", "wrist"),
    "hip_sag": ("shoulder", "hip", "ankle"),
    "hip_pike": ("shoulder", "hip", "ankle"),
    "knee_bend": ("hip", "knee", "ankle"),
    "head_position": ("ear", "shoulder", "hip"),
    "hand_placement": ("shoulder", "wrist"),
    # deadlift
    "start_back": ("shoulder", "hip"),
    "hips_shoot_up": ("shoulder", "hip"),
    "back_rounding": ("shoulder", "hip", "knee"),
    "lockout_arch": ("shoulder", "hip"),
    "hip_extension": ("shoulder", "hip", "knee"),
    "knee_lockout": ("hip", "knee", "ankle"),
    "arms_straight": ("shoulder", "elbow", "wrist"),
    "bar_start": ("wrist", "heel", "toe"),
    "bar_forward": ("wrist", "heel", "toe"),
    "start_knees": ("hip", "knee", "ankle"),
    # bicep curl
    "curl_top": ("shoulder", "elbow", "wrist"),
    "curl_bottom": ("shoulder", "elbow", "wrist"),
    "elbow_drift": ("hip", "shoulder", "elbow"),
    "torso_swing": ("shoulder", "hip"),
}


def highlighted_landmarks(rule_id: str, side: BodySide) -> tuple[LandmarkId, ...]:
    """Landmarks to mark when showing a mistake. Unknown rules highlight nothing."""
    joints = landmarks_for(side)
    ear = LandmarkId.LEFT_EAR if side is BodySide.LEFT else LandmarkId.RIGHT_EAR
    return tuple(
        ear if role == "ear" else getattr(joints, role) for role in _ROLES.get(rule_id, ())
    )