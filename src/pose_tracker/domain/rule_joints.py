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

    # bench press
    "bench_depth": ("shoulder", "elbow", "wrist"),
    "bench_lockout": ("shoulder", "elbow", "wrist"),
    "hips_lifted": ("shoulder", "hip"),
    "back_arch": ("shoulder", "hip"),
    "bar_path": ("wrist",),
    "bar_drift": ("wrist",),

    # lateral raise
    "raise_height": ("hip", "shoulder", "elbow"),
    "raise_too_high": ("hip", "shoulder", "elbow"),
    "arm_symmetry": ("shoulder", "elbow", "wrist"),
    "elbow_bend": ("shoulder", "elbow", "wrist"),
    "shrugging": ("ear", "shoulder"),
    "body_sway": ("shoulder", "hip"),
    
    # plank
    "support_position": ("shoulder", "elbow"),
    "hold_steady": ("shoulder", "hip", "ankle"),

    # lat pulldown
    "pulldown_depth": ("shoulder", "elbow"),
    "pulldown_stretch": ("shoulder", "elbow", "wrist"),
    "grip_width": ("wrist",),
    "bar_level": ("wrist",),
    # incline / decline press
    "bench_angle": ("shoulder", "hip"),
    # hip thrust
    "thrust_lockout": ("shoulder", "hip", "knee"),
    "foot_placement": ("knee", "ankle", "heel", "toe"),
    "thrust_tempo": ("hip",),
    # bent-over row
    "row_top": ("shoulder", "elbow", "wrist"),
    "row_stretch": ("shoulder", "elbow", "wrist"),
    "row_hinge": ("shoulder", "hip"),
    # calf raise
    "calf_height": ("ankle", "heel", "toe"),
    "calf_tempo": ("heel", "toe"),
}

# Rules about both sides of the body at once (front-view exercises).
_BILATERAL = frozenset({
    "raise_height", "raise_too_high", "arm_symmetry", "elbow_bend", "shrugging", "body_sway",
    "pulldown_depth", "pulldown_stretch", "grip_width", "bar_level",
})


def highlighted_landmarks(rule_id: str, side: BodySide) -> tuple[LandmarkId, ...]:
    """Landmarks to mark when showing a mistake. Unknown rules highlight nothing."""
    sides = (BodySide.LEFT, BodySide.RIGHT) if rule_id in _BILATERAL else (side,)
    return tuple(_landmark(role, s) for s in sides for role in _ROLES.get(rule_id, ()))


def _landmark(role: str, side: BodySide) -> LandmarkId:
    if role == "ear":
        return LandmarkId.LEFT_EAR if side is BodySide.LEFT else LandmarkId.RIGHT_EAR
    return getattr(landmarks_for(side), role)