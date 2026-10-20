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

def bench_pose(
    elbow_angle_deg: float,
    tilt_deg: float = 0.0,
    neck_angle_deg: float = 180.0,
    arm_tilt_deg: float = 0.0,
    direction: int = 1,
) -> Pose:
    """Left-side lifter lying down, seen from the side.

    direction: +1 = head toward image-right, -1 = image-left.
    tilt_deg: shoulder-hip line vs horizontal; > 0 = hips higher than the shoulders.
    arm_tilt_deg: tilts the press line away from vertical, toward the head if positive.
    """
    torso, upper, fore, head = 0.30, 0.15, 0.15, 0.10

    tilt = math.radians(tilt_deg)
    hip = (0.5, 0.65)
    shoulder = (hip[0] + direction * torso * math.cos(tilt), hip[1] + torso * math.sin(tilt))

    # The wrist rises along the press line; the elbow bends toward the feet.
    phi = math.radians(arm_tilt_deg)
    up = (direction * math.sin(phi), -math.cos(phi))
    normal = (-direction * math.cos(phi), -math.sin(phi))
    theta = math.radians(elbow_angle_deg)
    reach = math.sqrt(upper**2 + fore**2 - 2 * upper * fore * math.cos(theta))
    along = (upper**2 + reach**2 - fore**2) / (2 * reach)
    sideways = math.sqrt(max(upper**2 - along**2, 0.0))
    wrist = (shoulder[0] + reach * up[0], shoulder[1] + reach * up[1])
    elbow = (
        shoulder[0] + along * up[0] + sideways * normal[0],
        shoulder[1] + along * up[1] + sideways * normal[1],
    )

    # The head lifts off the body axis by (180 - neck angle).
    axis = (direction * math.cos(tilt), math.sin(tilt))
    beta = -direction * math.radians(180.0 - neck_angle_deg)
    ear = (
        shoulder[0] + head * (axis[0] * math.cos(beta) - axis[1] * math.sin(beta)),
        shoulder[1] + head * (axis[0] * math.sin(beta) + axis[1] * math.cos(beta)),
    )

    knee = (hip[0] - direction * 0.15, hip[1] - 0.12)
    ankle = (knee[0] - direction * 0.03, knee[1] + 0.22)

    landmarks = [Landmark(0.5, 0.5, 0.0, 1.0)] * 33
    placements = {
        LandmarkId.LEFT_SHOULDER: shoulder, LandmarkId.RIGHT_SHOULDER: shoulder,
        LandmarkId.LEFT_HIP: hip, LandmarkId.RIGHT_HIP: hip,
        LandmarkId.LEFT_ELBOW: elbow, LandmarkId.LEFT_WRIST: wrist,
        LandmarkId.LEFT_EAR: ear,
        LandmarkId.LEFT_KNEE: knee, LandmarkId.LEFT_ANKLE: ankle,
    }
    for landmark_id, (x, y) in placements.items():
        landmarks[landmark_id] = Landmark(x, y, 0.0, 1.0)
    return Pose(tuple(landmarks))

def _unit(vector: tuple[float, float]) -> tuple[float, float]:
    length = math.hypot(*vector)
    return vector[0] / length, vector[1] / length


def _turn(vector: tuple[float, float], radians: float) -> tuple[float, float]:
    cos, sin = math.cos(radians), math.sin(radians)
    return vector[0] * cos - vector[1] * sin, vector[0] * sin + vector[1] * cos


def front_pose(
    raise_left_deg: float,
    raise_right_deg: float | None = None,
    elbow_angle_deg: float = 170.0,
    shrug: float = 0.0,
    sway_deg: float = 0.0,
) -> Pose:
    """Person facing the camera (a FRONT view) with both arms visible.

    raise_*_deg: angle at the shoulder between the torso and the upper arm (0 = at the side).
    shrug: fraction by which the shoulders are lifted toward the ears.
    sway_deg: sideways lean of the upper body; > 0 leans toward image-right.
    """
    upper, fore = 0.15, 0.15
    raise_right = raise_left_deg if raise_right_deg is None else raise_right_deg
    sway = 0.30 * math.tan(math.radians(sway_deg))
    shoulder_y = 0.30 - shrug * 0.10
    bend = math.radians(180.0 - elbow_angle_deg)

    landmarks = [Landmark(0.5, 0.5, 0.0, 1.0)] * 33
    sides = (
        (-1, raise_left_deg, LandmarkId.LEFT_SHOULDER, LandmarkId.LEFT_ELBOW,
         LandmarkId.LEFT_WRIST, LandmarkId.LEFT_HIP, LandmarkId.LEFT_EAR),
        (1, raise_right, LandmarkId.RIGHT_SHOULDER, LandmarkId.RIGHT_ELBOW,
         LandmarkId.RIGHT_WRIST, LandmarkId.RIGHT_HIP, LandmarkId.RIGHT_EAR),
    )
    for sign, raise_deg, shoulder_id, elbow_id, wrist_id, hip_id, ear_id in sides:
        shoulder = (0.5 + sign * 0.10 + sway, shoulder_y)
        hip = (0.5 + sign * 0.07, 0.60)
        ear = (0.5 + sign * 0.04 + sway, 0.20)
        down = _unit((hip[0] - shoulder[0], hip[1] - shoulder[1]))
        # A positive turn moves a downward vector toward image-left: the left arm (sign -1)
        # turns by +raise and the right arm by -raise, so both move away from the body.
        upper_dir = _turn(down, -sign * math.radians(raise_deg))
        elbow = (shoulder[0] + upper * upper_dir[0], shoulder[1] + upper * upper_dir[1])
        fore_dir = _turn(upper_dir, -sign * bend)
        wrist = (elbow[0] + fore * fore_dir[0], elbow[1] + fore * fore_dir[1])
        for landmark_id, (x, y) in (
            (shoulder_id, shoulder), (hip_id, hip), (ear_id, ear),
            (elbow_id, elbow), (wrist_id, wrist),
        ):
            landmarks[landmark_id] = Landmark(x, y, 0.0, 1.0)
    return Pose(tuple(landmarks))


def plank_pose(
    hip_sag_deg: float = 0.0,
    knee_angle_deg: float = 180.0,
    neck_angle_deg: float = 180.0,
    elbow_ahead: float = 0.0,
    facing: int = 1,
) -> Pose:
    """Left-side forearm plank built on pushup_pose: the elbow sits ``elbow_ahead`` torso
    lengths ahead of (+) or behind (-) the shoulder, with the forearm flat on the floor."""
    base = pushup_pose(170, hip_sag_deg, knee_angle_deg, neck_angle_deg, 0.0, facing)
    shoulder = base.get(LandmarkId.LEFT_SHOULDER)
    elbow = Landmark(shoulder.x + facing * elbow_ahead * 0.25, shoulder.y + 0.12, 0.0, 1.0)
    wrist = Landmark(elbow.x + facing * 0.11, elbow.y, 0.0, 1.0)
    landmarks = list(base.landmarks)
    landmarks[LandmarkId.LEFT_ELBOW] = elbow
    landmarks[LandmarkId.LEFT_WRIST] = wrist
    return Pose(tuple(landmarks))

def pulldown_pose(
    elevation_deg: float,
    elbow_angle_deg: float = 175.0,
    grip_ratio: float | None = None,
    bar_tilt: float = 0.0,
) -> Pose:
    """Seated lifter facing the camera, both arms visible (a FRONT view).

    elevation_deg: each upper arm's angle from straight down (0 = hanging, 180 = overhead).
    grip_ratio: if given, the wrists are moved sideways to this spacing in shoulder widths.
    bar_tilt: lowers the right wrist by this much (an uneven bar), in image units.
    """
    upper, fore = 0.15, 0.15
    elevation = math.radians(elevation_deg)
    bend = math.radians(180.0 - elbow_angle_deg)

    landmarks = [Landmark(0.5, 0.5, 0.0, 1.0)] * 33
    sides = (
        (-1, LandmarkId.LEFT_SHOULDER, LandmarkId.LEFT_ELBOW, LandmarkId.LEFT_WRIST,
         LandmarkId.LEFT_HIP, LandmarkId.LEFT_EAR),
        (1, LandmarkId.RIGHT_SHOULDER, LandmarkId.RIGHT_ELBOW, LandmarkId.RIGHT_WRIST,
         LandmarkId.RIGHT_HIP, LandmarkId.RIGHT_EAR),
    )
    for sign, shoulder_id, elbow_id, wrist_id, hip_id, ear_id in sides:
        shoulder = (0.5 + sign * 0.10, 0.30)
        hip = (0.5 + sign * 0.07, 0.60)
        ear = (0.5 + sign * 0.04, 0.20)
        upper_dir = (sign * math.sin(elevation), math.cos(elevation))
        elbow = (shoulder[0] + upper * upper_dir[0], shoulder[1] + upper * upper_dir[1])
        fore_dir = _turn(upper_dir, -sign * bend)
        wrist = (elbow[0] + fore * fore_dir[0], elbow[1] + fore * fore_dir[1])
        if grip_ratio is not None:
            wrist = (0.5 + sign * grip_ratio * 0.10, wrist[1])
        if sign == 1:
            wrist = (wrist[0], wrist[1] + bar_tilt)
        for landmark_id, (x, y) in (
            (shoulder_id, shoulder), (hip_id, hip), (ear_id, ear),
            (elbow_id, elbow), (wrist_id, wrist),
        ):
            landmarks[landmark_id] = Landmark(x, y, 0.0, 1.0)
    return Pose(tuple(landmarks))


def thrust_pose(
    hip_angle_deg: float,
    shin_angle_deg: float = 10.0,
    neck_angle_deg: float = 170.0,
) -> Pose:
    """Side view of a hip thrust: upper back on the bench (left of the image), knees to the right.

    The torso slopes up toward the shoulders by up to 25 degrees with the hips low and is
    level when the hips are fully extended. shin_angle_deg is the shin's angle from vertical.
    """
    torso, thigh, shin, head = 0.30, 0.25, 0.25, 0.10
    slope = min(max((180.0 - hip_angle_deg) / 80.0, 0.0), 1.0)
    tilt = math.radians(-25.0 * slope)  # shoulder-hip line vs horizontal; negative = shoulders higher

    shoulder = (0.25, 0.50)
    hip = (shoulder[0] + torso * math.cos(tilt), shoulder[1] - torso * math.sin(tilt))
    back_to_shoulder = math.atan2(math.sin(tilt), -math.cos(tilt))  # direction hip -> shoulder
    thigh_dir = back_to_shoulder + math.radians(hip_angle_deg)
    knee = (hip[0] + thigh * math.cos(thigh_dir), hip[1] + thigh * math.sin(thigh_dir))
    shin_tilt = math.radians(shin_angle_deg)
    ankle = (knee[0] + shin * math.sin(shin_tilt), knee[1] + shin * math.cos(shin_tilt))
    ear_dir = -tilt + math.radians(neck_angle_deg)  # -tilt is the direction shoulder -> hip
    ear = (shoulder[0] + head * math.cos(ear_dir), shoulder[1] + head * math.sin(ear_dir))

    landmarks = [Landmark(0.5, 0.5, 0.0, 1.0)] * 33
    placements = {
        LandmarkId.LEFT_SHOULDER: shoulder, LandmarkId.RIGHT_SHOULDER: shoulder,
        LandmarkId.LEFT_HIP: hip, LandmarkId.RIGHT_HIP: hip,
        LandmarkId.LEFT_EAR: ear,
        LandmarkId.LEFT_KNEE: knee, LandmarkId.LEFT_ANKLE: ankle,
    }
    for landmark_id, (x, y) in placements.items():
        landmarks[landmark_id] = Landmark(x, y, 0.0, 1.0)
    return Pose(tuple(landmarks))


def calf_pose(
    foot_angle_deg: float,
    knee_angle_deg: float = 178.0,
    lean_deg: float = 0.0,
    facing: int = 1,
) -> Pose:
    """Left-side standing lifter. foot_angle_deg: heel-to-toe line vs horizontal (> 0 = heel raised).

    facing: +1 = faces image-right, -1 = image-left. lean_deg: forward trunk lean (> 0 = forward).
    """
    foot, shank, thigh, torso = 0.12, 0.22, 0.22, 0.30
    angle = math.radians(foot_angle_deg)
    toe = (0.5 + facing * 0.10, 0.92)
    heel = (toe[0] - facing * foot * math.cos(angle), toe[1] - foot * math.sin(angle))
    ankle = (heel[0] + facing * 0.02, heel[1] - 0.06)
    knee = (ankle[0], ankle[1] - shank)
    bend = math.radians(180.0 - knee_angle_deg)
    hip = (knee[0] + facing * thigh * math.sin(bend), knee[1] - thigh * math.cos(bend))
    lean = math.radians(lean_deg)
    shoulder = (hip[0] + facing * torso * math.sin(lean), hip[1] - torso * math.cos(lean))

    landmarks = [Landmark(0.5, 0.5, 0.0, 1.0)] * 33
    placements = {
        LandmarkId.LEFT_SHOULDER: shoulder, LandmarkId.RIGHT_SHOULDER: shoulder,
        LandmarkId.LEFT_HIP: hip, LandmarkId.RIGHT_HIP: hip,
        LandmarkId.LEFT_KNEE: knee, LandmarkId.LEFT_ANKLE: ankle,
        LandmarkId.LEFT_HEEL: heel, LandmarkId.LEFT_FOOT_INDEX: toe,
    }
    for landmark_id, (x, y) in placements.items():
        landmarks[landmark_id] = Landmark(x, y, 0.0, 1.0)
    return Pose(tuple(landmarks))