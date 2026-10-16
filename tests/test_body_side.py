from __future__ import annotations

from pose_tracker.domain.body_side import (
    LEFT_SIDE, RIGHT_SIDE, BodySide, landmarks_for, select_visible_side,
)
from pose_tracker.domain.pose import Landmark, Pose


def pose_with_visibility(left: float, right: float) -> Pose:
    landmarks = [Landmark(0.5, 0.5, 0.0, 1.0)] * 33
    for i in LEFT_SIDE.tracked():
        landmarks[i] = Landmark(0.5, 0.5, 0.0, left)
    for i in RIGHT_SIDE.tracked():
        landmarks[i] = Landmark(0.5, 0.5, 0.0, right)
    return Pose(tuple(landmarks))


def test_selects_more_visible_side() -> None:
    assert select_visible_side(pose_with_visibility(0.2, 0.9)) is BodySide.RIGHT
    assert select_visible_side(pose_with_visibility(0.9, 0.2)) is BodySide.LEFT


def test_tie_prefers_left() -> None:
    assert select_visible_side(pose_with_visibility(0.7, 0.7)) is BodySide.LEFT


def test_landmarks_for() -> None:
    assert landmarks_for(BodySide.LEFT) is LEFT_SIDE
    assert landmarks_for(BodySide.RIGHT) is RIGHT_SIDE