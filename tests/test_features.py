from __future__ import annotations

import pytest
from pose_factory import squat_pose, press_pose, pushup_pose, deadlift_pose, curl_pose
from pose_tracker.domain.body_side import BodySide
from pose_tracker.domain.features import compute_features
from pose_tracker.domain.pose import Landmark, LandmarkId, Pose



def test_knee_angle_and_torso_lean() -> None:
    f = compute_features(squat_pose(120, 30), BodySide.LEFT, 1.0, 0.5)
    assert f.knee_angle == pytest.approx(120)
    assert f.torso_lean_deg == pytest.approx(30)


def test_low_visibility_landmark_gives_none_only_for_affected_features() -> None:
    landmarks = list(squat_pose(120, 10).landmarks)
    landmarks[LandmarkId.LEFT_KNEE] = Landmark(0.5, 0.7, 0.0, 0.1)
    f = compute_features(Pose(tuple(landmarks)), BodySide.LEFT, 1.0, 0.5)
    assert f.knee_angle is None
    assert f.torso_lean_deg == pytest.approx(10)

@pytest.mark.parametrize(("facing", "layback", "expected"), [
    (1, 20, 20), (-1, 20, 20),   # leaning back reads positive whichever way you face
    (1, -10, -10), (-1, -10, -10),  # leaning forward reads negative
])
def test_signed_layback(facing: int, layback: float, expected: float) -> None:
    f = compute_features(press_pose(120, layback, facing), BodySide.LEFT, 1.0, 0.5)
    assert f.torso_layback_deg == pytest.approx(expected)


def test_layback_unknown_when_facing_is_unclear() -> None:
    f = compute_features(squat_pose(120), BodySide.LEFT, 1.0, 0.5)
    assert f.torso_layback_deg is None


def test_elbow_angle_and_hand_position() -> None:
    f = compute_features(press_pose(180), BodySide.LEFT, 1.0, 0.5)
    assert f.elbow_angle == pytest.approx(180)
    assert f.hand_x == pytest.approx(0.0)
    assert f.hand_y == pytest.approx((0.65 - 0.0) / 0.30)  # wrist 0.35 above the shoulder

def test_plank_features_for_a_straight_body() -> None:
    f = compute_features(pushup_pose(170), BodySide.LEFT, 1.0, 0.5)
    assert f.elbow_angle == pytest.approx(170)
    assert f.body_incline_deg == pytest.approx(0)
    assert f.hip_sag_deg == pytest.approx(0)
    assert f.hand_offset == pytest.approx(0)
    assert f.neck_angle == pytest.approx(180)
    assert f.knee_angle == pytest.approx(180)


@pytest.mark.parametrize(("facing", "sag"), [(1, 20), (-1, 20), (1, -20), (-1, -20)])
def test_hip_sag_is_signed_whichever_way_you_face(facing: int, sag: float) -> None:
    f = compute_features(
        pushup_pose(170, hip_sag_deg=sag, facing=facing), BodySide.LEFT, 1.0, 0.5
    )
    assert f.hip_sag_deg == pytest.approx(sag)


@pytest.mark.parametrize("facing", [1, -1])
def test_hand_offset_is_positive_when_hands_are_ahead_of_the_shoulders(facing: int) -> None:
    f = compute_features(
        pushup_pose(170, hand_ahead=0.4, facing=facing), BodySide.LEFT, 1.0, 0.5
    )
    assert f.hand_offset == pytest.approx(0.4)


def test_neck_angle_drops_when_the_head_droops() -> None:
    f = compute_features(pushup_pose(170, neck_angle_deg=120), BodySide.LEFT, 1.0, 0.5)
    assert f.neck_angle == pytest.approx(120)


def test_upright_body_has_a_steep_incline() -> None:
    f = compute_features(press_pose(120), BodySide.LEFT, 1.0, 0.5)
    assert f.body_incline_deg == pytest.approx(90)

@pytest.mark.parametrize("facing", [1, -1])
def test_deadlift_features(facing: int) -> None:
    pose = deadlift_pose(
        100, torso_deg=40, chord_shrink=0.1, bar_offset=0.25,
        neck_angle_deg=165, facing=facing,
    )
    f = compute_features(pose, BodySide.LEFT, 1.0, 0.5)
    assert f.hip_angle == pytest.approx(100)
    assert f.torso_lean_deg == pytest.approx(40)
    assert f.torso_layback_deg == pytest.approx(-40)  # leaning forward is negative
    assert f.torso_thigh_ratio == pytest.approx(0.30 * 0.9 / 0.25)
    assert f.bar_offset == pytest.approx(0.25)
    assert f.neck_angle == pytest.approx(165)

@pytest.mark.parametrize("facing", [1, -1])
def test_curl_features(facing: int) -> None:
    pose = curl_pose(90, upper_arm_deg=20, layback_deg=8, facing=facing)
    f = compute_features(pose, BodySide.LEFT, 1.0, 0.5)
    assert f.elbow_angle == pytest.approx(90)
    assert f.upper_arm_angle == pytest.approx(20)
    assert f.torso_layback_deg == pytest.approx(8)