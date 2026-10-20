from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from pose_tracker.domain.body_side import (
    BodySide,
    SideLandmarks,
    landmarks_for,
    select_visible_side,
)
from pose_tracker.domain.geometry import Point2D, distance
from pose_tracker.domain.pose import Landmark, LandmarkId, Pose
from pose_tracker.domain.geometry import Point2D, angle_at, distance

_BASE_LANDMARKS = int(LandmarkId.NECK)  # the model's own landmarks; derived ones follow

# Landmarks that move together.
_ABOVE_HIPS: tuple[int, ...] = (
    *range(LandmarkId.LEFT_HIP), LandmarkId.NECK, LandmarkId.MOUTH_CENTER,
)
_HIPS: tuple[int, ...] = (LandmarkId.LEFT_HIP, LandmarkId.RIGHT_HIP)
_UPPER_BODY: tuple[int, ...] = (*_ABOVE_HIPS, *_HIPS)
_HEAD: tuple[int, ...] = (*range(LandmarkId.LEFT_SHOULDER), LandmarkId.MOUTH_CENTER)
_HAND = {
    BodySide.LEFT: (LandmarkId.LEFT_PINKY, LandmarkId.LEFT_INDEX, LandmarkId.LEFT_THUMB),
    BodySide.RIGHT: (LandmarkId.RIGHT_PINKY, LandmarkId.RIGHT_INDEX, LandmarkId.RIGHT_THUMB),
}
_EAR = {BodySide.LEFT: LandmarkId.LEFT_EAR, BodySide.RIGHT: LandmarkId.RIGHT_EAR}
_LEGS: tuple[int, ...] = tuple(range(LandmarkId.LEFT_HIP, LandmarkId.RIGHT_FOOT_INDEX + 1))

@dataclass(slots=True)
class _Skeleton:
    """The pose in image proportions (x scaled by width / height), edited in place."""

    points: list[Point2D]
    side: BodySide
    joints: SideLandmarks


# -- geometry --------------------------------------------------------------------------


def _vector(origin: Point2D, target: Point2D) -> Point2D:
    return Point2D(target.x - origin.x, target.y - origin.y)


def _signed_angle(first: Point2D, second: Point2D) -> float:
    """Signed angle in radians from one vector to another."""
    return math.atan2(
        first.x * second.y - first.y * second.x, first.x * second.x + first.y * second.y
    )


def _rotated(point: Point2D, pivot: Point2D, radians: float) -> Point2D:
    dx, dy = point.x - pivot.x, point.y - pivot.y
    cos, sin = math.cos(radians), math.sin(radians)
    return Point2D(pivot.x + dx * cos - dy * sin, pivot.y + dx * sin + dy * cos)


def _angle_delta(
    pivot: Point2D, fixed: Point2D, moving: Point2D, target_deg: float
) -> float | None:
    """Rotation of ``moving`` about ``pivot`` that makes the angle fixed-pivot-moving equal
    ``target_deg``, keeping the side it is already on. None if a segment has no length."""
    if distance(pivot, fixed) == 0.0 or distance(pivot, moving) == 0.0:
        return None
    current = _signed_angle(_vector(pivot, fixed), _vector(pivot, moving))
    target = math.radians(min(max(target_deg, 0.0), 180.0))
    return math.copysign(target, current) - current


def _rotate(skeleton: _Skeleton, ids: Sequence[int], pivot: Point2D, radians: float) -> None:
    for i in ids:
        if i < len(skeleton.points):
            skeleton.points[i] = _rotated(skeleton.points[i], pivot, radians)


def _translate(skeleton: _Skeleton, ids: Sequence[int], dx: float, dy: float) -> None:
    for i in ids:
        if i < len(skeleton.points):
            point = skeleton.points[i]
            skeleton.points[i] = Point2D(point.x + dx, point.y + dy)


def _swing(
    skeleton: _Skeleton,
    pivot: Point2D,
    fixed: Point2D,
    moving: Point2D,
    target_deg: float,
    group: Sequence[int],
    follow: bool = False,
) -> bool:
    """Set the angle fixed-pivot-moving to ``target_deg``.

    The group rotates about the pivot with ``moving``. With ``follow`` the group instead
    keeps its orientation and is shifted by however far ``moving`` travels.
    """
    delta = _angle_delta(pivot, fixed, moving, target_deg)
    if delta is None:
        return False
    if follow:
        new = _rotated(moving, pivot, delta)
        _translate(skeleton, group, new.x - moving.x, new.y - moving.y)
    else:
        _rotate(skeleton, group, pivot, delta)
    return True


# -- one corrector per kind of mistake ---------------------------------------------------


def _knee_with_body(s: _Skeleton, limit: float) -> bool:
    """Thigh swings about the knee; hips and upper body follow. Feet stay planted."""
    j, p = s.joints, s.points
    return _swing(s, p[j.knee], p[j.ankle], p[j.hip], limit, _UPPER_BODY, follow=True)


def _knee_with_foot(s: _Skeleton, limit: float) -> bool:
    """Shin swings about the knee; hips and upper body stay put."""
    j, p = s.joints, s.points
    return _swing(s, p[j.knee], p[j.hip], p[j.ankle], limit, (j.ankle, j.heel, j.toe))


def _elbow(s: _Skeleton, limit: float) -> bool:
    """Forearm and hand swing about the elbow; the upper arm stays put."""
    j, p = s.joints, s.points
    return _swing(s, p[j.elbow], p[j.shoulder], p[j.wrist], limit, (j.wrist, *_HAND[s.side]))


def _hip_opening(s: _Skeleton, limit: float) -> bool:
    """Everything above the hips swings about the hip to open the shoulder-hip-knee angle."""
    j, p = s.joints, s.points
    return _swing(s, p[j.hip], p[j.knee], p[j.shoulder], limit, _ABOVE_HIPS)


def _neck(s: _Skeleton, limit: float) -> bool:
    """The head swings about the shoulder to set the ear-shoulder-hip angle."""
    j, p = s.joints, s.points
    return _swing(s, p[j.shoulder], p[j.hip], p[_EAR[s.side]], limit, _HEAD)


def _torso_tilt(s: _Skeleton, limit: float) -> bool:
    """Everything above the hips swings about the hip until the trunk is ``limit`` from vertical."""
    j, p = s.joints, s.points
    hip = p[j.hip]
    straight_up = Point2D(hip.x, hip.y - 1.0)  # image y grows downward
    delta = _angle_delta(hip, straight_up, p[j.shoulder], limit)
    if delta is None:
        return False
    _rotate(s, _ABOVE_HIPS, hip, delta)
    return True


def _hip_line(s: _Skeleton, limit: float) -> bool:
    """Hips move onto the straight line from shoulder to ankle (the limit is not needed)."""
    j, p = s.joints, s.points
    shoulder, hip, ankle = p[j.shoulder], p[j.hip], p[j.ankle]
    axis = _vector(shoulder, ankle)
    length_squared = axis.x**2 + axis.y**2
    if length_squared == 0.0:
        return False
    along = ((hip.x - shoulder.x) * axis.x + (hip.y - shoulder.y) * axis.y) / length_squared
    on_line = Point2D(shoulder.x + along * axis.x, shoulder.y + along * axis.y)
    _translate(s, _HIPS, on_line.x - hip.x, on_line.y - hip.y)
    return True


def _hand_offset(s: _Skeleton, limit: float) -> bool:
    """The arm swings about the shoulder until the wrist sits ``limit`` torso lengths
    ahead of the shoulder along the body (negative = behind)."""
    j, p = s.joints, s.points
    shoulder, hip, wrist, ankle = p[j.shoulder], p[j.hip], p[j.wrist], p[j.ankle]
    torso, reach = distance(shoulder, hip), distance(shoulder, wrist)
    if torso == 0.0 or reach == 0.0 or distance(shoulder, ankle) == 0.0:
        return False
    cosine = limit * torso / reach
    if abs(cosine) > 1.0:
        return False  # the arm is too short to reach that position
    toward_head = _vector(ankle, shoulder)
    current = _signed_angle(toward_head, _vector(shoulder, wrist))
    delta = math.copysign(math.acos(cosine), current) - current
    _rotate(s, (j.elbow, j.wrist, *_HAND[s.side]), shoulder, delta)
    return True

def _upper_arm(s: _Skeleton, limit: float) -> bool:
    """The whole arm swings about the shoulder until the upper arm is ``limit`` from the torso line."""
    j, p = s.joints, s.points
    return _swing(
        s, p[j.shoulder], p[j.hip], p[j.elbow], limit, (j.elbow, j.wrist, *_HAND[s.side])
    )

def _level_back(s: _Skeleton, limit: float) -> bool:
    """Hips and legs shift vertically until the shoulder-hip line is level (limit not needed)."""
    j, p = s.joints, s.points
    shoulder, hip = p[j.shoulder], p[j.hip]
    if distance(shoulder, hip) == 0.0:
        return False
    _translate(s, _LEGS, 0.0, shoulder.y - hip.y)
    return True

def _for_both_sides(s: _Skeleton, corrector: Corrector, limit: float) -> bool:
    """Apply a one-sided corrector to the left arm/leg and then to the right one."""
    done = False
    for side in (BodySide.LEFT, BodySide.RIGHT):
        done = corrector(_Skeleton(s.points, side, landmarks_for(side)), limit) or done
    return done


def _raise_both(s: _Skeleton, limit: float) -> bool:
    """Both arms swing about their shoulders to the same raise angle."""
    return _for_both_sides(s, _upper_arm, limit)


def _elbows_both(s: _Skeleton, limit: float) -> bool:
    """Both forearms swing about their elbows to the same elbow angle."""
    return _for_both_sides(s, _elbow, limit)


def _match_arms(s: _Skeleton, limit: float) -> bool:
    """The lagging arm swings up to within ``limit`` degrees of the higher arm."""
    arms = []
    for side in (BodySide.LEFT, BodySide.RIGHT):
        j = landmarks_for(side)
        try:
            arms.append((angle_at(s.points[j.hip], s.points[j.shoulder], s.points[j.elbow]), side))
        except ValueError:
            return False
    (_, low_side), (high_angle, _) = sorted(arms, key=lambda arm: arm[0])
    lagging = _Skeleton(s.points, low_side, landmarks_for(low_side))
    return _upper_arm(lagging, high_angle - limit)

def _arm_from_down(s: _Skeleton, limit: float) -> bool:
    """The arm swings about the shoulder until the upper arm is ``limit`` degrees from straight down."""
    j, p = s.joints, s.points
    shoulder = p[j.shoulder]
    down = Point2D(shoulder.x, shoulder.y + 1.0)  # image y grows downward
    return _swing(s, shoulder, down, p[j.elbow], limit, (j.elbow, j.wrist, *_HAND[s.side]))


def _arms_from_down(s: _Skeleton, limit: float) -> bool:
    return _for_both_sides(s, _arm_from_down, limit)

Corrector = Callable[[_Skeleton, float], bool]

_CORRECTORS: dict[str, Corrector] = {
    # squat
    "squat_depth": _knee_with_body,
    "torso_lean": _torso_tilt,
    # shoulder press
    "press_bottom": _elbow,
    "press_lockout": _elbow,
    "layback": _torso_tilt,
    # push-up
    "pushup_depth": _elbow,
    "pushup_lockout": _elbow,
    "hip_sag": _hip_line,
    "hip_pike": _hip_line,
    "knee_bend": _knee_with_foot,
    "head_position": _neck,  # also used by the deadlift
    "hand_placement": _hand_offset,
    # deadlift
    "start_back": _torso_tilt,
    "lockout_arch": _torso_tilt,
    "hip_extension": _hip_opening,
    "knee_lockout": _knee_with_body,
    "arms_straight": _elbow,
    "start_knees": _knee_with_body,
    
    # bicep curl
    "curl_top": _elbow,
    "curl_bottom": _elbow,
    "elbow_drift": _upper_arm,

    # bench press
    "bench_depth": _elbow,
    "bench_lockout": _elbow,
    "hips_lifted": _level_back,
    "back_arch": _level_back,

    # lateral raise
    "raise_height": _raise_both,
    "raise_too_high": _raise_both,
    "arm_symmetry": _match_arms,
    "elbow_bend": _elbows_both,

    # lat pulldown
    "pulldown_depth": _arms_from_down,
    "pulldown_stretch": _elbows_both,
    
    # bent-over row
    "row_top": _elbow,
    "row_stretch": _elbow,
    "row_hinge": _torso_tilt,
}


def has_corrected_pose(rule_id: str) -> bool:
    return rule_id in _CORRECTORS


def corrected_pose(
    rule_id: str, pose: Pose, limit: float, aspect_ratio: float
) -> Pose | None:
    """Where the body should have been for the rule to pass, on the same body.

    Limb lengths are kept and only the segments the rule is about move. ``limit`` is
    the rule's own limit as stored with the mistake. Returns None if the rule has no
    corrected pose or the pose cannot be corrected (missing landmarks, zero-length limbs).
    """
    corrector = _CORRECTORS.get(rule_id)
    if corrector is None or aspect_ratio <= 0.0 or len(pose.landmarks) < _BASE_LANDMARKS:
        return None
    side = select_visible_side(pose)
    skeleton = _Skeleton(
        [Point2D(lm.x * aspect_ratio, lm.y) for lm in pose.landmarks],
        side,
        landmarks_for(side),
    )
    if not corrector(skeleton, limit):
        return None
    return Pose(
        tuple(
            Landmark(point.x / aspect_ratio, point.y, original.z, original.visibility)
            for point, original in zip(skeleton.points, pose.landmarks, strict=True)
        )
    )