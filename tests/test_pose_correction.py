from __future__ import annotations

import math

import pytest
from pose_factory import ( 
    deadlift_pose, press_pose, pushup_pose, squat_pose, curl_pose, 
    bench_pose, front_pose, plank_pose, pulldown_pose, 
    thrust_pose, calf_pose)

from pose_tracker.config import AppConfig
from pose_tracker.domain.body_side import BodySide
from pose_tracker.domain.exercises.catalog import build_catalog
from pose_tracker.domain.features import BodyFeatures, compute_features
from pose_tracker.domain.pose import Landmark, LandmarkId, Pose
from pose_tracker.domain.pose_correction import corrected_pose, has_corrected_pose

L = LandmarkId

# Movement over time, or no absolute target stored: no corrected pose.
NO_GHOST = {
    "control", "bar_path", "leg_drive", "hips_shoot_up", "back_rounding",
    "bar_start", "bar_forward", "torso_swing", "bar_drift",
    "shrugging", "body_sway", "support_position", "hold_steady",
    "bench_angle", "grip_width", "bar_level", "thrust_lockout", "foot_placement",
    "thrust_tempo", "calf_height", "calf_tempo",
}


def measure(pose: Pose, aspect: float = 1.0) -> BodyFeatures:
    return compute_features(pose, BodySide.LEFT, aspect, 0.5)


def xy(pose: Pose, landmark_id: LandmarkId) -> tuple[float, float]:
    landmark = pose.get(landmark_id)
    return landmark.x, landmark.y


def ghost_of(rule_id: str, pose: Pose, limit: float, aspect: float = 1.0) -> Pose:
    ghost = corrected_pose(rule_id, pose, limit, aspect)
    assert ghost is not None
    return ghost


def test_every_rule_is_either_correctable_or_explicitly_excluded() -> None:
    config = AppConfig()
    catalog = build_catalog(config.squat, config.shoulder_press, config.push_up, config.deadlift)
    for exercise in catalog.values():
        for rule in exercise.rules:
            assert has_corrected_pose(rule.rule_id) == (rule.rule_id not in NO_GHOST), rule.rule_id


# -- squat -----------------------------------------------------------------------------


def test_squat_depth_ghost_reaches_the_target_and_keeps_the_torso_angle() -> None:
    pose = squat_pose(120, lean_deg=30)
    ghost = ghost_of("squat_depth", pose, 100.0)
    assert measure(ghost).knee_angle == pytest.approx(100)
    assert measure(ghost).torso_lean_deg == pytest.approx(measure(pose).torso_lean_deg)
    assert xy(ghost, L.LEFT_KNEE) == pytest.approx(xy(pose, L.LEFT_KNEE))
    assert xy(ghost, L.LEFT_ANKLE) == pytest.approx(xy(pose, L.LEFT_ANKLE))
    assert xy(ghost, L.LEFT_HIP) != pytest.approx(xy(pose, L.LEFT_HIP))


def test_torso_lean_ghost_stands_at_the_allowed_lean_in_the_same_direction() -> None:
    pose = squat_pose(120, lean_deg=70)
    ghost = ghost_of("torso_lean", pose, 50.0)
    assert measure(ghost).torso_lean_deg == pytest.approx(50)
    assert xy(ghost, L.LEFT_HIP) == pytest.approx(xy(pose, L.LEFT_HIP))
    assert ghost.get(L.LEFT_SHOULDER).x > ghost.get(L.LEFT_HIP).x


# -- shoulder press / shared elbow rules -------------------------------------------------


@pytest.mark.parametrize("facing", [1, -1])
def test_layback_ghost_leans_back_by_exactly_the_limit(facing: int) -> None:
    pose = press_pose(150, layback_deg=25, facing=facing)
    assert measure(ghost_of("layback", pose, 15.0)).torso_layback_deg == pytest.approx(15)


@pytest.mark.parametrize(("rule_id", "elbow", "limit"), [
    ("press_bottom", 130, 100.0),
    ("press_lockout", 150, 165.0),
    ("pushup_depth", 120, 95.0),
    ("arms_straight", 140, 160.0),
])
def test_elbow_rules_set_the_angle_and_leave_the_upper_arm_alone(
    rule_id: str, elbow: float, limit: float
) -> None:
    pose = press_pose(elbow)
    ghost = ghost_of(rule_id, pose, limit)
    assert measure(ghost).elbow_angle == pytest.approx(limit)
    assert xy(ghost, L.LEFT_SHOULDER) == pytest.approx(xy(pose, L.LEFT_SHOULDER))
    assert xy(ghost, L.LEFT_ELBOW) == pytest.approx(xy(pose, L.LEFT_ELBOW))
    assert xy(ghost, L.LEFT_WRIST) != pytest.approx(xy(pose, L.LEFT_WRIST))


# -- deadlift --------------------------------------------------------------------------


def test_hip_extension_ghost_opens_the_hip_to_the_limit() -> None:
    pose = deadlift_pose(150, torso_deg=30, knee_angle_deg=160)
    ghost = ghost_of("hip_extension", pose, 170.0)
    assert measure(ghost).hip_angle == pytest.approx(170)
    assert xy(ghost, L.LEFT_HIP) == pytest.approx(xy(pose, L.LEFT_HIP))
    assert xy(ghost, L.LEFT_KNEE) == pytest.approx(xy(pose, L.LEFT_KNEE))


@pytest.mark.parametrize(("rule_id", "knee", "limit"), [
    ("knee_lockout", 150, 170.0),
    ("start_knees", 80, 100.0),
    ("squat_depth", 120, 100.0),
])
def test_knee_rules_set_the_angle_move_the_body_and_keep_the_feet_planted(
    rule_id: str, knee: float, limit: float
) -> None:
    pose = deadlift_pose(100, knee_angle_deg=knee)
    ghost = ghost_of(rule_id, pose, limit)
    assert measure(ghost).knee_angle == pytest.approx(limit)
    assert measure(ghost).torso_lean_deg == pytest.approx(measure(pose).torso_lean_deg)
    assert xy(ghost, L.LEFT_KNEE) == pytest.approx(xy(pose, L.LEFT_KNEE))
    assert xy(ghost, L.LEFT_ANKLE) == pytest.approx(xy(pose, L.LEFT_ANKLE))
    assert xy(ghost, L.LEFT_HIP) != pytest.approx(xy(pose, L.LEFT_HIP))


@pytest.mark.parametrize(("rule_id", "start", "limit"), [
    ("start_back", 80, 70.0),
    ("lockout_arch", 20, 5.0),
])
def test_deadlift_back_rules_set_the_trunk_angle(rule_id: str, start: float, limit: float) -> None:
    pose = deadlift_pose(120, torso_deg=start)
    ghost = ghost_of(rule_id, pose, limit)
    assert measure(ghost).torso_lean_deg == pytest.approx(limit)
    assert xy(ghost, L.LEFT_HIP) == pytest.approx(xy(pose, L.LEFT_HIP))


# -- push-up ---------------------------------------------------------------------------


def test_head_position_ghost_lifts_the_head_to_the_limit() -> None:
    pose = pushup_pose(170, neck_angle_deg=120)
    ghost = ghost_of("head_position", pose, 145.0)
    assert measure(ghost).neck_angle == pytest.approx(145)
    assert xy(ghost, L.LEFT_SHOULDER) == pytest.approx(xy(pose, L.LEFT_SHOULDER))


def test_knee_bend_ghost_straightens_the_shin_about_the_knee() -> None:
    pose = pushup_pose(170, knee_angle_deg=130)
    ghost = ghost_of("knee_bend", pose, 160.0)
    assert measure(ghost).knee_angle == pytest.approx(160)
    assert xy(ghost, L.LEFT_HIP) == pytest.approx(xy(pose, L.LEFT_HIP))
    assert xy(ghost, L.LEFT_KNEE) == pytest.approx(xy(pose, L.LEFT_KNEE))


@pytest.mark.parametrize(("rule_id", "sag"), [("hip_sag", 25), ("hip_pike", -25)])
def test_hip_ghost_puts_the_hips_on_the_shoulder_ankle_line(rule_id: str, sag: float) -> None:
    pose = pushup_pose(170, hip_sag_deg=sag)
    ghost = ghost_of(rule_id, pose, 12.0)
    assert measure(pose).hip_sag_deg == pytest.approx(sag)
    assert measure(ghost).hip_sag_deg == pytest.approx(0, abs=1e-6)
    assert xy(ghost, L.LEFT_SHOULDER) == pytest.approx(xy(pose, L.LEFT_SHOULDER))
    assert xy(ghost, L.LEFT_ANKLE) == pytest.approx(xy(pose, L.LEFT_ANKLE))


@pytest.mark.parametrize(("ahead", "limit"), [(0.5, 0.3), (-0.5, -0.3)])
def test_hand_ghost_puts_the_wrist_at_the_edge_of_the_allowed_band(
    ahead: float, limit: float
) -> None:
    pose = pushup_pose(170, hand_ahead=ahead)
    ghost = ghost_of("hand_placement", pose, limit)
    assert measure(pose).hand_offset == pytest.approx(ahead)
    assert measure(ghost).hand_offset == pytest.approx(limit)
    assert xy(ghost, L.LEFT_SHOULDER) == pytest.approx(xy(pose, L.LEFT_SHOULDER))

    def arm_length(p: Pose) -> float:
        (sx, sy), (wx, wy) = xy(p, L.LEFT_SHOULDER), xy(p, L.LEFT_WRIST)
        return math.hypot(wx - sx, wy - sy)

    assert arm_length(ghost) == pytest.approx(arm_length(pose))


# -- edge cases --------------------------------------------------------------------------


def test_rules_without_a_ghost_return_none() -> None:
    assert corrected_pose("control", squat_pose(120), 0.0, 1.0) is None
    assert corrected_pose("made_up", squat_pose(120), 0.0, 1.0) is None
    assert not has_corrected_pose("control")


def test_too_few_landmarks_or_a_bad_aspect_ratio_gives_none() -> None:
    assert corrected_pose("squat_depth", Pose(()), 100.0, 1.0) is None
    assert corrected_pose("squat_depth", squat_pose(120), 100.0, 0.0) is None


def test_coincident_joints_give_none() -> None:
    stacked = Pose(tuple(Landmark(0.5, 0.5, 0.0, 1.0) for _ in range(35)))
    assert corrected_pose("squat_depth", stacked, 100.0, 1.0) is None
    assert corrected_pose("hip_sag", stacked, 12.0, 1.0) is None


def test_angles_are_corrected_in_image_proportions() -> None:
    aspect = 16 / 9
    ghost = ghost_of("squat_depth", squat_pose(120), 100.0, aspect)
    assert measure(ghost, aspect).knee_angle == pytest.approx(100)


def test_depth_and_visibility_survive_the_correction() -> None:
    pose = squat_pose(120)
    ghost = ghost_of("squat_depth", pose, 100.0)
    assert len(ghost.landmarks) == len(pose.landmarks)
    assert [(lm.z, lm.visibility) for lm in ghost.landmarks] == [
        (lm.z, lm.visibility) for lm in pose.landmarks
    ]
@pytest.mark.parametrize(("rule_id", "elbow", "limit"), [
    ("curl_top", 80, 55.0),
    ("curl_bottom", 140, 160.0),
])
def test_curl_elbow_ghosts_set_the_angle_and_keep_the_upper_arm_still(
    rule_id: str, elbow: float, limit: float
) -> None:
    pose = curl_pose(elbow)
    ghost = ghost_of(rule_id, pose, limit)
    assert measure(ghost).elbow_angle == pytest.approx(limit)
    assert xy(ghost, L.LEFT_SHOULDER) == pytest.approx(xy(pose, L.LEFT_SHOULDER))
    assert xy(ghost, L.LEFT_ELBOW) == pytest.approx(xy(pose, L.LEFT_ELBOW))
    assert xy(ghost, L.LEFT_WRIST) != pytest.approx(xy(pose, L.LEFT_WRIST))


def test_elbow_drift_ghost_pins_the_upper_arm_and_carries_the_forearm() -> None:
    pose = curl_pose(90, upper_arm_deg=50)
    ghost = ghost_of("elbow_drift", pose, 30.0)
    assert measure(ghost).upper_arm_angle == pytest.approx(30)
    assert measure(ghost).elbow_angle == pytest.approx(90)  # the arm moves as one piece
    assert xy(ghost, L.LEFT_SHOULDER) == pytest.approx(xy(pose, L.LEFT_SHOULDER))
    assert xy(ghost, L.LEFT_ELBOW) != pytest.approx(xy(pose, L.LEFT_ELBOW))

@pytest.mark.parametrize(("rule_id", "elbow", "limit"), [
    ("bench_depth", 120, 90.0),
    ("bench_lockout", 150, 165.0),
])
def test_bench_elbow_ghosts_set_the_angle_and_keep_the_upper_arm_still(
    rule_id: str, elbow: float, limit: float
) -> None:
    pose = bench_pose(elbow)
    ghost = ghost_of(rule_id, pose, limit)
    assert measure(ghost).elbow_angle == pytest.approx(limit)
    assert xy(ghost, L.LEFT_SHOULDER) == pytest.approx(xy(pose, L.LEFT_SHOULDER))
    assert xy(ghost, L.LEFT_ELBOW) == pytest.approx(xy(pose, L.LEFT_ELBOW))


@pytest.mark.parametrize(("rule_id", "tilt"), [("hips_lifted", 20), ("back_arch", -20)])
def test_back_ghost_levels_the_hips_and_carries_the_legs(rule_id: str, tilt: float) -> None:
    pose = bench_pose(120, tilt_deg=tilt)
    ghost = ghost_of(rule_id, pose, 12.0)

    def knee_offset(p: Pose) -> tuple[float, float]:
        return (
            p.get(L.LEFT_KNEE).x - p.get(L.LEFT_HIP).x,
            p.get(L.LEFT_KNEE).y - p.get(L.LEFT_HIP).y,
        )

    assert measure(pose).back_tilt_deg == pytest.approx(tilt)
    assert measure(ghost).back_tilt_deg == pytest.approx(0, abs=1e-6)
    assert xy(ghost, L.LEFT_SHOULDER) == pytest.approx(xy(pose, L.LEFT_SHOULDER))
    assert xy(ghost, L.LEFT_HIP) != pytest.approx(xy(pose, L.LEFT_HIP))
    assert knee_offset(ghost) == pytest.approx(knee_offset(pose))

@pytest.mark.parametrize(("rule_id", "start", "limit"), [
    ("raise_height", 55, 80.0),
    ("raise_too_high", 125, 105.0),
])
def test_raise_ghosts_swing_both_arms_to_the_limit(rule_id: str, start: float, limit: float) -> None:
    pose = front_pose(start)
    ghost = ghost_of(rule_id, pose, limit)
    assert measure(ghost).arm_raise_deg == pytest.approx(limit)
    assert measure(ghost).arm_asymmetry_deg == pytest.approx(0, abs=1e-6)
    assert xy(ghost, L.LEFT_SHOULDER) == pytest.approx(xy(pose, L.LEFT_SHOULDER))
    assert xy(ghost, L.LEFT_ELBOW) != pytest.approx(xy(pose, L.LEFT_ELBOW))
    assert xy(ghost, L.RIGHT_ELBOW) != pytest.approx(xy(pose, L.RIGHT_ELBOW))


def test_arm_symmetry_ghost_raises_the_lagging_arm_to_within_the_limit() -> None:
    pose = front_pose(100, 60)
    ghost = ghost_of("arm_symmetry", pose, 15.0)
    assert measure(pose).arm_asymmetry_deg == pytest.approx(40)
    assert measure(ghost).arm_asymmetry_deg == pytest.approx(15)
    assert xy(ghost, L.LEFT_ELBOW) == pytest.approx(xy(pose, L.LEFT_ELBOW))  # the higher arm stays
    assert xy(ghost, L.RIGHT_ELBOW) != pytest.approx(xy(pose, L.RIGHT_ELBOW))


def test_elbow_bend_ghost_straightens_both_forearms_to_the_limit() -> None:
    pose = front_pose(60, elbow_angle_deg=90)
    ghost = ghost_of("elbow_bend", pose, 120.0)
    assert measure(ghost).arm_bend_deg == pytest.approx(120)
    assert xy(ghost, L.LEFT_ELBOW) == pytest.approx(xy(pose, L.LEFT_ELBOW))
    assert xy(ghost, L.LEFT_WRIST) != pytest.approx(xy(pose, L.LEFT_WRIST))

def test_pulldown_depth_ghost_swings_both_arms_down_to_the_limit() -> None:
    pose = pulldown_pose(110, 140.0)
    ghost = ghost_of("pulldown_depth", pose, 65.0)
    assert measure(ghost).arm_elevation_deg == pytest.approx(65)
    assert measure(ghost).arm_bend_deg == pytest.approx(measure(pose).arm_bend_deg)  # arms move as one piece
    assert xy(ghost, L.LEFT_SHOULDER) == pytest.approx(xy(pose, L.LEFT_SHOULDER))
    assert xy(ghost, L.LEFT_ELBOW) != pytest.approx(xy(pose, L.LEFT_ELBOW))
    assert xy(ghost, L.RIGHT_ELBOW) != pytest.approx(xy(pose, L.RIGHT_ELBOW))


@pytest.mark.parametrize(("rule_id", "elbow", "limit"), [
    ("row_top", 120, 105.0),
    ("row_stretch", 140, 160.0),
])
def test_row_elbow_ghosts_set_the_angle(rule_id: str, elbow: float, limit: float) -> None:
    assert measure(ghost_of(rule_id, press_pose(elbow), limit)).elbow_angle == pytest.approx(limit)


def test_row_hinge_ghost_tilts_the_torso_to_the_limit() -> None:
    pose = deadlift_pose(130, torso_deg=15)
    ghost = ghost_of("row_hinge", pose, 30.0)
    assert measure(ghost).torso_lean_deg == pytest.approx(30)
    assert xy(ghost, L.LEFT_HIP) == pytest.approx(xy(pose, L.LEFT_HIP))