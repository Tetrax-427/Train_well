from __future__ import annotations

import math

from pose_tracker.domain.pose import Landmark, LandmarkId, Pose


def squat_pose(knee_angle_deg: float, lean_deg: float = 10.0, shoulder_gap: float = 0.0) -> Pose:
    """Left-side pose. gap=0 reads as a SIDE view; gap=0.3 reads as FRONT."""
    knee = (0.5, 0.7)
    ankle = (0.5, 0.9)
    theta = math.radians(knee_angle_deg)
    hip = (knee[0] + 0.2 * math.sin(theta), knee[1] + 0.2 * math.cos(theta))
    lean = math.radians(lean_deg)
    shoulder = (hip[0] + 0.3 * math.sin(lean), hip[1] - 0.3 * math.cos(lean))

    landmarks = [Landmark(0.5, 0.5, 0.0, 1.0)] * 33

    def put(landmark_id: LandmarkId, xy: tuple[float, float], dx: float = 0.0) -> None:
        landmarks[landmark_id] = Landmark(xy[0] + dx, xy[1], 0.0, 1.0)

    put(LandmarkId.LEFT_SHOULDER, shoulder)
    put(LandmarkId.RIGHT_SHOULDER, shoulder, shoulder_gap)
    put(LandmarkId.LEFT_HIP, hip)
    put(LandmarkId.RIGHT_HIP, hip, shoulder_gap)
    put(LandmarkId.LEFT_KNEE, knee)
    put(LandmarkId.LEFT_ANKLE, ankle)
    return Pose(tuple(landmarks))

def press_pose(
    elbow_angle_deg: float,
    layback_deg: float = 0.0,
    facing: int = 1,
    knee_angle_deg: float = 180.0,
) -> Pose:
    """Left-side pose of an ideal press: the wrist rises straight above the shoulder.

    facing: +1 = person faces image-right, -1 = image-left.
    layback_deg: > 0 leans the torso back, < 0 forward.
    """
    upper, fore, torso, thigh = 0.18, 0.17, 0.30, 0.20

    hip = (0.5, 0.65)
    layback = math.radians(layback_deg)
    shoulder = (hip[0] - facing * torso * math.sin(layback), hip[1] - torso * math.cos(layback))

    theta = math.radians(elbow_angle_deg)
    reach = math.sqrt(upper**2 + fore**2 - 2 * upper * fore * math.cos(theta))
    along = (upper**2 + reach**2 - fore**2) / (2 * reach)
    sideways = math.sqrt(max(upper**2 - along**2, 0.0))
    wrist = (shoulder[0], shoulder[1] - reach)
    elbow = (shoulder[0] + facing * sideways, shoulder[1] - along)

    knee_theta = math.radians(knee_angle_deg)
    knee = (hip[0], hip[1] + thigh)
    ankle = (
        knee[0] + facing * thigh * math.sin(knee_theta),
        knee[1] - thigh * math.cos(knee_theta),
    )
    heel = (ankle[0] - facing * 0.03, ankle[1] + 0.03)
    toe = (ankle[0] + facing * 0.07, ankle[1] + 0.03)

    landmarks = [Landmark(0.5, 0.5, 0.0, 1.0)] * 33
    placements = {
        LandmarkId.LEFT_SHOULDER: shoulder, LandmarkId.RIGHT_SHOULDER: shoulder,
        LandmarkId.LEFT_HIP: hip, LandmarkId.RIGHT_HIP: hip,
        LandmarkId.LEFT_ELBOW: elbow, LandmarkId.LEFT_WRIST: wrist,
        LandmarkId.LEFT_KNEE: knee, LandmarkId.LEFT_ANKLE: ankle,
        LandmarkId.LEFT_HEEL: heel, LandmarkId.LEFT_FOOT_INDEX: toe,
    }
    for landmark_id, (x, y) in placements.items():
        landmarks[landmark_id] = Landmark(x, y, 0.0, 1.0)
    return Pose(tuple(landmarks))

def pushup_pose(
    elbow_angle_deg: float,
    hip_sag_deg: float = 0.0,
    knee_angle_deg: float = 180.0,
    neck_angle_deg: float = 180.0,
    hand_ahead: float = 0.0,
    facing: int = 1,
) -> Pose:
    """Left-side plank. facing: +1 = head toward image-right, -1 = image-left.

    hip_sag_deg > 0 drops the hips, < 0 raises them. hand_ahead is how far the wrist
    is ahead of the shoulder along the body, in torso lengths.
    """
    upper, fore, torso, thigh, shin, head = 0.12, 0.11, 0.25, 0.20, 0.20, 0.10
    shoulder = (0.5 + facing * 0.3, 0.45)

    # Arm: wrist planted below (and optionally ahead of) the shoulder.
    theta = math.radians(elbow_angle_deg)
    reach = math.sqrt(upper**2 + fore**2 - 2 * upper * fore * math.cos(theta))
    ahead = hand_ahead * torso
    drop = math.sqrt(max(reach**2 - ahead**2, 0.0))
    wrist = (shoulder[0] + facing * ahead, shoulder[1] + drop)
    along = (upper**2 + reach**2 - fore**2) / (2 * reach)
    perp = math.sqrt(max(upper**2 - along**2, 0.0))
    ux, uy = (wrist[0] - shoulder[0]) / reach, (wrist[1] - shoulder[1]) / reach
    elbow = (
        shoulder[0] + along * ux - facing * perp * uy,
        shoulder[1] + along * uy + facing * perp * ux,
    )

    # Body: bending by hip_sag_deg at the hip and by (180 - knee angle) at the knee.
    half = math.radians(hip_sag_deg) / 2

    def step(origin: tuple[float, float], length: float, slope: float) -> tuple[float, float]:
        return (
            origin[0] - facing * length * math.cos(slope),
            origin[1] + length * math.sin(slope),
        )

    hip = step(shoulder, torso, half)
    knee = step(hip, thigh, -half)
    ankle = step(knee, shin, -half - math.radians(180.0 - knee_angle_deg))

    # Head: droops downward by (180 - neck angle).
    heading = math.radians(180.0 - neck_angle_deg) - half
    ear = (
        shoulder[0] + facing * head * math.cos(heading),
        shoulder[1] + head * math.sin(heading),
    )

    landmarks = [Landmark(0.5, 0.5, 0.0, 1.0)] * 33
    placements = {
        LandmarkId.LEFT_SHOULDER: shoulder, LandmarkId.RIGHT_SHOULDER: shoulder,
        LandmarkId.LEFT_HIP: hip, LandmarkId.RIGHT_HIP: hip,
        LandmarkId.LEFT_ELBOW: elbow, LandmarkId.LEFT_WRIST: wrist,
        LandmarkId.LEFT_KNEE: knee, LandmarkId.LEFT_ANKLE: ankle,
        LandmarkId.LEFT_EAR: ear,
    }
    for landmark_id, (x, y) in placements.items():
        landmarks[landmark_id] = Landmark(x, y, 0.0, 1.0)
    return Pose(tuple(landmarks))

def deadlift_pose(
    hip_angle_deg: float,
    torso_deg: float = 45.0,
    knee_angle_deg: float = 150.0,
    chord_shrink: float = 0.0,
    neck_angle_deg: float = 180.0,
    elbow_angle_deg: float = 180.0,
    bar_offset: float = 0.0,
    facing: int = 1,
) -> Pose:
    """Left-side lifter. facing: +1 = faces image-right, -1 = image-left.

    torso_deg: torso from vertical, forward positive (negative = leaning back).
    chord_shrink: fraction by which the shoulder-hip chord is shortened (spine flexion proxy).
    bar_offset: wrist ahead (+) or behind (-) mid-foot, in (shrunk) torso lengths.
    """
    torso, thigh, shin, upper, fore, head = 0.30, 0.25, 0.25, 0.15, 0.15, 0.10

    def polar(origin: tuple[float, float], length: float, angle_deg: float) -> tuple[float, float]:
        a = math.radians(angle_deg)  # image-plane angle for a person facing right
        return origin[0] + facing * length * math.cos(a), origin[1] + length * math.sin(a)

    hip = (0.5, 0.45)
    lean = math.radians(torso_deg)
    torso_dir = math.degrees(math.atan2(-math.cos(lean), math.sin(lean)))
    chord = torso * (1.0 - chord_shrink)
    shoulder = polar(hip, chord, torso_dir)
    thigh_dir = torso_dir + hip_angle_deg
    knee = polar(hip, thigh, thigh_dir)
    ankle = polar(knee, shin, thigh_dir + (180.0 - knee_angle_deg))
    ear = polar(shoulder, head, torso_dir + (180.0 - neck_angle_deg))
    elbow = (shoulder[0], shoulder[1] + upper)
    wrist = polar(elbow, fore, 90.0 - (180.0 - elbow_angle_deg))

    mid_foot_x = wrist[0] - facing * bar_offset * chord
    heel = (mid_foot_x - facing * 0.05, ankle[1] + 0.02)
    toe = (mid_foot_x + facing * 0.05, ankle[1] + 0.02)

    landmarks = [Landmark(0.5, 0.5, 0.0, 1.0)] * 33
    placements = {
        LandmarkId.LEFT_SHOULDER: shoulder, LandmarkId.RIGHT_SHOULDER: shoulder,
        LandmarkId.LEFT_HIP: hip, LandmarkId.RIGHT_HIP: hip,
        LandmarkId.LEFT_ELBOW: elbow, LandmarkId.LEFT_WRIST: wrist,
        LandmarkId.LEFT_KNEE: knee, LandmarkId.LEFT_ANKLE: ankle,
        LandmarkId.LEFT_HEEL: heel, LandmarkId.LEFT_FOOT_INDEX: toe,
        LandmarkId.LEFT_EAR: ear,
    }
    for landmark_id, (x, y) in placements.items():
        landmarks[landmark_id] = Landmark(x, y, 0.0, 1.0)
    return Pose(tuple(landmarks))
def curl_pose(
    elbow_angle_deg: float,
    upper_arm_deg: float = 5.0,
    layback_deg: float = 0.0,
    facing: int = 1,
) -> Pose:
    """Left-side standing lifter. facing: +1 = faces image-right, -1 = image-left.

    upper_arm_deg: angle at the shoulder between the torso and the upper arm.
    layback_deg: > 0 leans the torso back, < 0 forward.
    """
    torso, upper, fore, thigh, shin = 0.30, 0.15, 0.15, 0.25, 0.25

    hip = (0.5, 0.40)
    layback = math.radians(layback_deg)
    shoulder = (hip[0] - facing * torso * math.sin(layback), hip[1] - torso * math.cos(layback))

    # Directions are measured from straight down, toward the way the person faces.
    upper_dir = layback + math.radians(upper_arm_deg)
    elbow = (
        shoulder[0] + facing * upper * math.sin(upper_dir),
        shoulder[1] + upper * math.cos(upper_dir),
    )
    fore_dir = upper_dir + math.radians(180.0 - elbow_angle_deg)
    wrist = (
        elbow[0] + facing * fore * math.sin(fore_dir),
        elbow[1] + fore * math.cos(fore_dir),
    )

    knee = (hip[0], hip[1] + thigh)
    ankle = (knee[0], knee[1] + shin)
    heel = (ankle[0] - facing * 0.03, ankle[1] + 0.02)
    toe = (ankle[0] + facing * 0.08, ankle[1] + 0.02)

    landmarks = [Landmark(0.5, 0.5, 0.0, 1.0)] * 33
    placements = {
        LandmarkId.LEFT_SHOULDER: shoulder, LandmarkId.RIGHT_SHOULDER: shoulder,
        LandmarkId.LEFT_HIP: hip, LandmarkId.RIGHT_HIP: hip,
        LandmarkId.LEFT_ELBOW: elbow, LandmarkId.LEFT_WRIST: wrist,
        LandmarkId.LEFT_KNEE: knee, LandmarkId.LEFT_ANKLE: ankle,
        LandmarkId.LEFT_HEEL: heel, LandmarkId.LEFT_FOOT_INDEX: toe,
    }
    for landmark_id, (x, y) in placements.items():
        landmarks[landmark_id] = Landmark(x, y, 0.0, 1.0)
    return Pose(tuple(landmarks))