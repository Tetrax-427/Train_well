from __future__ import annotations

import math
from dataclasses import dataclass

from pose_tracker.domain.body_side import BodySide, SideLandmarks, landmarks_for
from pose_tracker.domain.geometry import Point2D, angle_at, distance, to_point
from pose_tracker.domain.pose import LandmarkId, Pose


@dataclass(frozen=True, slots=True)
class BodyFeatures:
    """Measurements for one side of the body. None means not measurable this frame.

    hand_x / hand_y are the wrist position relative to the hip in torso lengths,
    in the image plane (x grows to the right of the image, y grows upward).
    """

    knee_angle: float | None
    torso_lean_deg: float | None  # trunk angle from vertical, unsigned; 0 = upright
    elbow_angle: float | None = None
    torso_layback_deg: float | None = None  # signed: > 0 leaning back, < 0 leaning forward
    hand_x: float | None = None
    hand_y: float | None = None
    # Plank (push-up) measurements
    body_incline_deg: float | None = None  # shoulder->ankle line vs horizontal; 0 = flat
    hip_sag_deg: float | None = None  # > 0 hips below the shoulder-ankle line, < 0 above
    hand_offset: float | None = None  # wrist vs shoulder along the body, torso lengths; > 0 = ahead
    neck_angle: float | None = None  # ear-shoulder-hip; 180 = head in line with the back
    # Deadlift measurements
    hip_angle: float | None = None  # shoulder-hip-knee; 180 = fully extended
    torso_thigh_ratio: float | None = None  # shoulder-hip chord / hip-knee length (spine proxy)
    bar_offset: float | None = None  # wrist vs mid-foot, torso lengths; > 0 = ahead of mid-foot
    # Curl measurement
    upper_arm_angle: float | None = None  # hip-shoulder-elbow; 0 = arm hanging along the torso

def compute_features(
    pose: Pose, side: BodySide, aspect_ratio: float, min_visibility: float
) -> BodyFeatures:
    joints = landmarks_for(side)
    hand_x, hand_y = _hand_position(pose, joints, aspect_ratio, min_visibility)
    return BodyFeatures(
        knee_angle=_joint_angle(
            pose, (joints.hip, joints.knee, joints.ankle), aspect_ratio, min_visibility
        ),
        torso_lean_deg=_torso_lean(
            pose, joints.shoulder, joints.hip, aspect_ratio, min_visibility
        ),
        elbow_angle=_joint_angle(
            pose, (joints.shoulder, joints.elbow, joints.wrist), aspect_ratio, min_visibility
        ),
        torso_layback_deg=_torso_layback(pose, side, aspect_ratio, min_visibility),
        hand_x=hand_x,
        hand_y=hand_y,
        body_incline_deg=_body_incline(pose, joints, aspect_ratio, min_visibility),
        hip_sag_deg=_hip_sag(pose, joints, aspect_ratio, min_visibility),
        hand_offset=_hand_offset(pose, joints, aspect_ratio, min_visibility),
        neck_angle=_joint_angle(
            pose, (_ear_id(side), joints.shoulder, joints.hip), aspect_ratio, min_visibility
        ),
                hip_angle=_joint_angle(
            pose, (joints.shoulder, joints.hip, joints.knee), aspect_ratio, min_visibility
        ),
        torso_thigh_ratio=_torso_thigh_ratio(pose, joints, aspect_ratio, min_visibility),
        bar_offset=_bar_offset(pose, side, joints, aspect_ratio, min_visibility),
        upper_arm_angle=_joint_angle(
            pose, (joints.hip, joints.shoulder, joints.elbow), aspect_ratio, min_visibility
        ),
    )


def _points(
    pose: Pose, ids: tuple[LandmarkId, ...], aspect_ratio: float, min_visibility: float
) -> list[Point2D] | None:
    landmarks = [pose.get(i) for i in ids]
    if any(lm.visibility < min_visibility for lm in landmarks):
        return None
    return [to_point(lm, aspect_ratio) for lm in landmarks]


def _joint_angle(
    pose: Pose, ids: tuple[LandmarkId, LandmarkId, LandmarkId],
    aspect_ratio: float, min_visibility: float,
) -> float | None:
    points = _points(pose, ids, aspect_ratio, min_visibility)
    if points is None:
        return None
    try:
        return angle_at(points[0], points[1], points[2])
    except ValueError:
        return None


def _torso_lean(
    pose: Pose, shoulder_id: LandmarkId, hip_id: LandmarkId,
    aspect_ratio: float, min_visibility: float,
) -> float | None:
    points = _points(pose, (shoulder_id, hip_id), aspect_ratio, min_visibility)
    if points is None:
        return None
    shoulder, hip = points
    straight_up = Point2D(hip.x, hip.y - 1.0)  # image y grows downward
    try:
        return angle_at(shoulder, hip, straight_up)
    except ValueError:
        return None


def _facing(pose: Pose, side: BodySide, min_visibility: float) -> int | None:
    """+1 if the person faces image-right, -1 if image-left, None if unclear.

    Feet are the stronger signal (heel -> toe); nose vs ear is the fallback.
    """
    joints = landmarks_for(side)
    ear = LandmarkId.LEFT_EAR if side is BodySide.LEFT else LandmarkId.RIGHT_EAR
    for back_id, front_id, margin in (
        (joints.heel, joints.toe, 0.02),
        (ear, LandmarkId.NOSE, 0.008),
    ):
        back, front = pose.get(back_id), pose.get(front_id)
        if min(back.visibility, front.visibility) >= min_visibility and abs(front.x - back.x) >= margin:
            return 1 if front.x > back.x else -1
    return None


def _torso_layback(
    pose: Pose, side: BodySide, aspect_ratio: float, min_visibility: float
) -> float | None:
    facing = _facing(pose, side, min_visibility)
    if facing is None:
        return None
    joints = landmarks_for(side)
    points = _points(pose, (joints.shoulder, joints.hip), aspect_ratio, min_visibility)
    if points is None:
        return None
    shoulder, hip = points
    forward = facing * (shoulder.x - hip.x)
    up = hip.y - shoulder.y
    if forward == 0.0 and up == 0.0:
        return None
    return math.degrees(math.atan2(0.0 - forward, up))


def _hand_position(
    pose: Pose, joints: SideLandmarks, aspect_ratio: float, min_visibility: float
) -> tuple[float | None, float | None]:
    points = _points(
        pose, (joints.shoulder, joints.hip, joints.wrist), aspect_ratio, min_visibility
    )
    if points is None:
        return None, None
    shoulder, hip, wrist = points
    torso = distance(shoulder, hip)
    if torso == 0.0:
        return None, None
    return (wrist.x - hip.x) / torso, (hip.y - wrist.y) / torso

def _ear_id(side: BodySide) -> LandmarkId:
    return LandmarkId.LEFT_EAR if side is BodySide.LEFT else LandmarkId.RIGHT_EAR


def _body_incline(
    pose: Pose, joints: SideLandmarks, aspect_ratio: float, min_visibility: float
) -> float | None:
    points = _points(pose, (joints.shoulder, joints.ankle), aspect_ratio, min_visibility)
    if points is None:
        return None
    shoulder, ankle = points
    run, rise = abs(ankle.x - shoulder.x), abs(ankle.y - shoulder.y)
    if run == 0.0 and rise == 0.0:
        return None
    return math.degrees(math.atan2(rise, run))


def _hip_sag(
    pose: Pose, joints: SideLandmarks, aspect_ratio: float, min_visibility: float
) -> float | None:
    """Deviation of the hip from the shoulder-ankle line in degrees, positive when below it."""
    points = _points(
        pose, (joints.shoulder, joints.hip, joints.ankle), aspect_ratio, min_visibility
    )
    if points is None:
        return None
    shoulder, hip, ankle = points
    run = ankle.x - shoulder.x
    if abs(run) < 1e-6:
        return None  # body is not horizontal, so "below the line" is meaningless
    try:
        deviation = 180.0 - angle_at(shoulder, hip, ankle)
    except ValueError:
        return None
    line_y = shoulder.y + (hip.x - shoulder.x) * (ankle.y - shoulder.y) / run
    return deviation if hip.y > line_y else -deviation  # image y grows downward


def _hand_offset(
    pose: Pose, joints: SideLandmarks, aspect_ratio: float, min_visibility: float
) -> float | None:
    """Wrist position relative to the shoulder along the body axis, in torso lengths.

    Positive means the hand is ahead of the shoulder (toward the head).
    """
    points = _points(
        pose, (joints.shoulder, joints.hip, joints.wrist, joints.ankle),
        aspect_ratio, min_visibility,
    )
    if points is None:
        return None
    shoulder, hip, wrist, ankle = points
    torso, axis = distance(shoulder, hip), distance(shoulder, ankle)
    if torso == 0.0 or axis == 0.0:
        return None
    toward_head = ((shoulder.x - ankle.x) / axis, (shoulder.y - ankle.y) / axis)
    along = (wrist.x - shoulder.x) * toward_head[0] + (wrist.y - shoulder.y) * toward_head[1]
    return along / torso

def _torso_thigh_ratio(
    pose: Pose, joints: SideLandmarks, aspect_ratio: float, min_visibility: float
) -> float | None:
    """Both segments lie in the sagittal plane, so for a rigid back this ratio is constant
    whatever the posture. A rounded or arched spine shortens the shoulder-hip chord."""
    points = _points(pose, (joints.shoulder, joints.hip, joints.knee), aspect_ratio, min_visibility)
    if points is None:
        return None
    shoulder, hip, knee = points
    thigh = distance(hip, knee)
    if thigh == 0.0:
        return None
    return distance(shoulder, hip) / thigh


def _bar_offset(
    pose: Pose, side: BodySide, joints: SideLandmarks, aspect_ratio: float, min_visibility: float
) -> float | None:
    """Horizontal distance of the wrist from mid-foot in torso lengths, positive ahead of the feet."""
    facing = _facing(pose, side, min_visibility)
    if facing is None:
        return None
    points = _points(
        pose, (joints.shoulder, joints.hip, joints.wrist, joints.heel, joints.toe),
        aspect_ratio, min_visibility,
    )
    if points is None:
        return None
    shoulder, hip, wrist, heel, toe = points
    torso = distance(shoulder, hip)
    if torso == 0.0:
        return None
    return facing * (wrist.x - (heel.x + toe.x) / 2) / torso