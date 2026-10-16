from __future__ import annotations

import pytest

from pose_tracker.domain.view import (
    CameraView, StableViewDetector, ViewDetector, ViewThresholds,
)
from pose_tracker.domain.pose import Landmark, LandmarkId, Pose

TORSO = 0.3


def make_pose(shoulder_width: float, visibility: float = 1.0) -> Pose:
    landmarks = [Landmark(0.5, 0.5, 0.0, visibility)] * 33
    half = shoulder_width / 2
    landmarks[LandmarkId.LEFT_SHOULDER] = Landmark(0.5 - half, 0.3, 0.0, visibility)
    landmarks[LandmarkId.RIGHT_SHOULDER] = Landmark(0.5 + half, 0.3, 0.0, visibility)
    landmarks[LandmarkId.LEFT_HIP] = Landmark(0.5 - half, 0.3 + TORSO, 0.0, visibility)
    landmarks[LandmarkId.RIGHT_HIP] = Landmark(0.5 + half, 0.3 + TORSO, 0.0, visibility)
    return Pose(tuple(landmarks))


@pytest.mark.parametrize(
    ("shoulder_width", "expected"),
    [
        (0.30, CameraView.FRONT),   # ratio 1.0
        (0.12, CameraView.ANGLED),  # ratio 0.4
        (0.05, CameraView.SIDE),    # ratio ~0.17
    ],
)
def test_detects_view(shoulder_width: float, expected: CameraView) -> None:
    assert ViewDetector().detect(make_pose(shoulder_width), aspect_ratio=1.0) is expected


def test_low_visibility_is_unknown() -> None:
    assert ViewDetector().detect(make_pose(0.3, visibility=0.2), 1.0) is CameraView.UNKNOWN


def test_aspect_ratio_changes_classification() -> None:
    pose = make_pose(0.12)
    detector = ViewDetector()
    assert detector.detect(pose, aspect_ratio=1.0) is CameraView.ANGLED
    assert detector.detect(pose, aspect_ratio=2.0) is CameraView.FRONT  # ratio 0.8


def test_invalid_thresholds_rejected() -> None:
    with pytest.raises(ValueError):
        ViewThresholds(front_min_ratio=0.2, side_max_ratio=0.3)


def test_stable_detector_requires_consecutive_frames() -> None:
    stable = StableViewDetector(ViewDetector(), frames_to_switch=3)
    front, side = make_pose(0.30), make_pose(0.05)

    assert stable.update(front, 1.0) is CameraView.UNKNOWN
    assert stable.update(front, 1.0) is CameraView.UNKNOWN
    assert stable.update(front, 1.0) is CameraView.FRONT

    assert stable.update(side, 1.0) is CameraView.FRONT  # a single blip is ignored
    assert stable.update(front, 1.0) is CameraView.FRONT


def test_stable_detector_treats_missing_pose_as_unknown() -> None:
    stable = StableViewDetector(ViewDetector(), frames_to_switch=2)
    front = make_pose(0.30)
    stable.update(front, 1.0)
    stable.update(front, 1.0)
    assert stable.view is CameraView.FRONT

    stable.update(None, 1.0)
    assert stable.update(None, 1.0) is CameraView.UNKNOWN